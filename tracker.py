#!/usr/bin/env python3
"""
Analytics, Simple HTML Report & Local Browser GUI for Smart Expense & Budget Tracker.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from database import (
    VALID_CATEGORIES,
    add_expense,
    fetch_category_summary,
    get_connection,
    set_category_budget,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "expenses.db"
DEFAULT_HTML = BASE_DIR / "dashboard.html"


def detect_high_value_outliers(conn: sqlite3.Connection, year_month: str, multiplier: float = 2.0) -> list[dict]:
    """
    Find individual expenses in YYYY-MM that are at least `multiplier` times
    larger than the average expense in their category.
    """
    rows = conn.execute(
        """
        SELECT
            e.id,
            e.title,
            e.category,
            e.amount,
            e.spent_on,
            cat_stats.cat_avg
        FROM expenses e
        INNER JOIN (
            SELECT category, AVG(amount) AS cat_avg
            FROM expenses
            WHERE substr(spent_on, 1, 7) = ?
            GROUP BY category
        ) cat_stats ON e.category = cat_stats.category
        WHERE substr(e.spent_on, 1, 7) = ?
          AND e.amount >= (cat_stats.cat_avg * ?)
        ORDER BY e.amount DESC
        """,
        (year_month, year_month, multiplier),
    ).fetchall()

    return [
        {
            "id": int(r["id"]),
            "title": r["title"],
            "category": r["category"],
            "amount": float(r["amount"]),
            "spent_on": r["spent_on"],
            "category_average": round(float(r["cat_avg"]), 2),
        }
        for r in rows
    ]


def fetch_recent_expenses(conn: sqlite3.Connection, year_month: str) -> list[dict]:
    """Fetch all expenses for a given YYYY-MM month ordered by newest date first."""
    rows = conn.execute(
        """
        SELECT id, title, category, amount, spent_on, payment_mode
        FROM expenses
        WHERE substr(spent_on, 1, 7) = ?
        ORDER BY spent_on DESC, id DESC
        """,
        (year_month,),
    ).fetchall()
    return [dict(r) for r in rows]


def build_monthly_report(conn: sqlite3.Connection, year_month: str) -> dict:
    """Compile monthly analytics report with budget alerts, outliers, and expense list."""
    categories = fetch_category_summary(conn, year_month)
    total_spent = round(sum(c["total_spent"] for c in categories), 2)
    total_tx = sum(c["tx_count"] for c in categories)
    alerts = [
        f"{c['category']}: Spent Rs {c['total_spent']} / Rs {c['budget_limit']} ({c['status']})"
        for c in categories
        if c["status"] in ("OVER_BUDGET", "WARNING_NEAR_LIMIT")
    ]
    outliers = detect_high_value_outliers(conn, year_month)
    expenses = fetch_recent_expenses(conn, year_month)

    return {
        "month": year_month,
        "total_spent": total_spent,
        "total_transactions": total_tx,
        "top_category": categories[0]["category"] if categories else None,
        "categories": categories,
        "budget_alerts": alerts,
        "unusual_high_expenses": outliers,
        "expenses": expenses,
    }


def render_html_page(report: dict, include_forms: bool = False) -> str:
    """Build a simple, clean student-style HTML page for the expense tracker."""
    options_html = "".join(f'<option value="{cat}">{cat}</option>' for cat in VALID_CATEGORIES)

    forms_section = ""
    if include_forms:
        forms_section = f"""
  <div class="forms-row">
    <form class="box" method="POST" action="/add-expense">
      <h3>Add New Expense</h3>
      <label>Title: <input type="text" name="title" placeholder="e.g. Canteen Lunch" required></label>
      <label>Category: <select name="category">{options_html}</select></label>
      <label>Amount (Rs): <input type="number" step="0.01" min="1" name="amount" required></label>
      <label>Date: <input type="date" name="spent_on" value="{report['month']}-15" required></label>
      <label>Payment Mode:
        <select name="payment_mode"><option>UPI</option><option>Card</option><option>Cash</option></select>
      </label>
      <button type="submit">Add Expense</button>
    </form>

    <form class="box" method="POST" action="/set-budget">
      <h3>Set Monthly Category Budget</h3>
      <label>Category: <select name="category">{options_html}</select></label>
      <label>Monthly Limit (Rs): <input type="number" step="0.01" min="1" name="monthly_limit" required></label>
      <button type="submit">Save Budget</button>
    </form>
  </div>
"""

    cat_rows = "".join(
        f"<tr><td>{c['category']}</td><td>{c['tx_count']}</td>"
        f"<td>Rs {c['total_spent']:.2f}</td><td>Rs {c['budget_limit']:.2f}</td>"
        f"<td>{c['utilization_pct']}%</td><td><b>{c['status']}</b></td></tr>"
        for c in report["categories"]
    ) or '<tr><td colspan="6">No expenses recorded yet.</td></tr>'

    exp_rows = "".join(
        f"<tr><td>{e['spent_on']}</td><td>{e['title']}</td><td>{e['category']}</td>"
        f"<td>Rs {e['amount']:.2f}</td><td>{e['payment_mode']}</td></tr>"
        for e in report.get("expenses", [])
    ) or '<tr><td colspan="5">No transactions found.</td></tr>'

    alerts_html = "".join(f"<li>{a}</li>" for a in report["budget_alerts"])
    alert_box = f'<div class="alert-box"><b>Budget Alerts:</b><ul>{alerts_html}</ul></div>' if alerts_html else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Smart Expense & Budget Tracker ({report['month']})</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 20px auto; padding: 0 15px; color: #222; background: #fafafa; }}
    h1, h2 {{ color: #1a365d; }}
    .summary-row, .forms-row {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
    .box {{ flex: 1; min-width: 220px; background: #fff; border: 1px solid #ccc; padding: 15px; border-radius: 6px; }}
    .alert-box {{ background: #fff3cd; border: 1px solid #ffecb5; padding: 12px; border-radius: 6px; margin-bottom: 20px; }}
    label {{ display: block; margin: 8px 0; font-size: 14px; }}
    input, select {{ width: 95%; padding: 6px; margin-top: 3px; }}
    button {{ margin-top: 10px; padding: 8px 14px; background: #2563eb; color: #fff; border: none; border-radius: 4px; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; margin-bottom: 25px; }}
    th, td {{ border: 1px solid #ddd; padding: 9px; text-align: left; font-size: 14px; }}
    th {{ background: #e2e8f0; }}
  </style>
</head>
<body>
  <h1>Smart Expense &amp; Budget Tracker ({report['month']})</h1>
  <div class="summary-row">
    <div class="box"><b>Total Spend:</b><br>Rs {report['total_spent']:.2f}</div>
    <div class="box"><b>Transactions:</b><br>{report['total_transactions']}</div>
    <div class="box"><b>Top Category:</b><br>{report['top_category'] or 'N/A'}</div>
  </div>
  {alert_box}
  {forms_section}
  <h2>Category Budget Summary</h2>
  <table>
    <thead><tr><th>Category</th><th>Count</th><th>Spent</th><th>Budget Limit</th><th>Used %</th><th>Status</th></tr></thead>
    <tbody>{cat_rows}</tbody>
  </table>
  <h2>All Expenses ({report['month']})</h2>
  <table>
    <thead><tr><th>Date</th><th>Title</th><th>Category</th><th>Amount</th><th>Mode</th></tr></thead>
    <tbody>{exp_rows}</tbody>
  </table>
</body>
</html>"""


def export_html_dashboard(report: dict, output_path: Path = DEFAULT_HTML) -> Path:
    """Save the HTML dashboard report to a file on disk."""
    output_path.write_text(render_html_page(report, include_forms=False), encoding="utf-8")
    return output_path


def seed_sample_data_if_empty(conn: sqlite3.Connection) -> None:
    """Insert sample data only if the expenses table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    if count > 0:
        return
    set_category_budget(conn, "Food", 4000)
    set_category_budget(conn, "Transport", 2000)
    set_category_budget(conn, "Education", 3000)

    sample_expenses = [
        ("College Canteen Lunch", "Food", 450, "2026-11-02", "UPI"),
        ("Monthly Grocery Pack", "Food", 1600, "2026-11-06", "Card"),
        ("Team Dinner Party", "Food", 2400, "2026-11-15", "UPI"),
        ("Metro Pass Recharge", "Transport", 600, "2026-11-03", "UPI"),
        ("Cloud & Python Reference Books", "Education", 1250, "2026-11-10", "Card"),
    ]
    for title, cat, amt, date_str, mode in sample_expenses:
        add_expense(conn, title, cat, amt, date_str, mode)


def start_web_gui(db_path: Path = DEFAULT_DB, port: int = 8000, month: str = "2026-11") -> None:
    """Start a simple local browser GUI at http://localhost:8000."""
    conn = get_connection(db_path)
    seed_sample_data_if_empty(conn)

    class ExpenseGUIHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            report = build_monthly_report(conn, month)
            html = render_html_page(report, include_forms=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            form = parse_qs(body)

            if self.path == "/add-expense":
                add_expense(
                    conn,
                    title=form.get("title", [""])[0],
                    category=form.get("category", ["Food"])[0],
                    amount=float(form.get("amount", ["0"])[0]),
                    spent_on=form.get("spent_on", [f"{month}-01"])[0],
                    payment_mode=form.get("payment_mode", ["UPI"])[0],
                )
            elif self.path == "/set-budget":
                set_category_budget(
                    conn,
                    category=form.get("category", ["Food"])[0],
                    monthly_limit=float(form.get("monthly_limit", ["1000"])[0]),
                )

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

        def log_message(self, fmt: str, *args) -> None:
            return

    url = f"http://localhost:{port}"
    print(f"Starting Expense Tracker Web GUI at {url} (Press Ctrl+C to stop)...")
    webbrowser.open(url)
    HTTPServer(("127.0.0.1", port), ExpenseGUIHandler).serve_forever()


def run_demo() -> dict:
    conn = get_connection(DEFAULT_DB)
    seed_sample_data_if_empty(conn)
    report = build_monthly_report(conn, "2026-11")
    html_file = export_html_dashboard(report, DEFAULT_HTML)
    print(json.dumps(report, indent=2))
    print(f"\nSaved visual HTML report to: {html_file}")
    print("Tip: Run `python tracker.py --gui` to open the interactive Web GUI in your browser!")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Expense & Budget Analytics Tracker")
    parser.add_argument("--gui", action="store_true", help="Launch interactive HTML Web GUI in browser")
    parser.add_argument("--port", type=int, default=8000, help="Port for Web GUI (default: 8000)")
    args = parser.parse_args()

    if args.gui:
        start_web_gui(port=args.port)
    else:
        run_demo()
