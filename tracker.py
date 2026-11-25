#!/usr/bin/env python3
"""
Analytics & HTML Dashboard Generator for Smart Expense & Budget Analytics Tracker.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from database import add_expense, fetch_category_summary, get_connection, set_category_budget


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


def build_monthly_report(conn: sqlite3.Connection, year_month: str) -> dict:
    """Compile complete monthly analytics report with budget alerts and outliers."""
    categories = fetch_category_summary(conn, year_month)
    total_spent = round(sum(c["total_spent"] for c in categories), 2)
    total_tx = sum(c["tx_count"] for c in categories)
    alerts = [
        f"{c['category']}: Spent Rs {c['total_spent']} against Rs {c['budget_limit']} limit ({c['status']})"
        for c in categories
        if c["status"] in ("OVER_BUDGET", "WARNING_NEAR_LIMIT")
    ]
    outliers = detect_high_value_outliers(conn, year_month)

    return {
        "month": year_month,
        "total_spent": total_spent,
        "total_transactions": total_tx,
        "top_category": categories[0]["category"] if categories else None,
        "categories": categories,
        "budget_alerts": alerts,
        "unusual_high_expenses": outliers,
    }


def export_html_dashboard(report: dict, output_path: Path) -> Path:
    """Render a clean single-file HTML summary dashboard for the monthly report."""
    rows_html = "".join(
        f"<tr><td>{c['category']}</td><td>{c['tx_count']}</td>"
        f"<td>Rs {c['total_spent']:.2f}</td><td>Rs {c['budget_limit']:.2f}</td>"
        f"<td>{c['utilization_pct']}%</td><td><strong>{c['status']}</strong></td></tr>"
        for c in report["categories"]
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Expense Analytics Report — {report['month']}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; color: #1e293b; }}
    .kpi {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
    .card {{ flex: 1; padding: 1rem; border: 1px solid #cbd5e1; border-radius: 8px; background: #f8fafc; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th, td {{ padding: 0.65rem; border-bottom: 1px solid #e2e8f0; text-align: left; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <h1>Smart Expense &amp; Budget Dashboard ({report['month']})</h1>
  <div class="kpi">
    <div class="card"><h3>Total Spend</h3><p>Rs {report['total_spent']:.2f}</p></div>
    <div class="card"><h3>Transactions</h3><p>{report['total_transactions']}</p></div>
    <div class="card"><h3>Top Category</h3><p>{report['top_category'] or 'N/A'}</p></div>
  </div>
  <h2>Category Breakdown</h2>
  <table>
    <thead><tr><th>Category</th><th>Count</th><th>Spent</th><th>Budget</th><th>Used %</th><th>Status</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")
    return output_path


def run_demo() -> dict:
    conn = get_connection(":memory:")
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

    return build_monthly_report(conn, "2026-11")


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
