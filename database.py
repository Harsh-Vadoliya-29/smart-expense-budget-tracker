"""
SQLite Database Layer for Smart Expense & Budget Analytics Tracker.
Handles table creation, parameterized CRUD queries, and SQL GROUP BY aggregations.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

VALID_CATEGORIES = ("Food", "Transport", "Rent", "Education", "Utilities", "Shopping", "Other")


def get_connection(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Create a SQLite connection with dictionary-like Row access."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create expenses and category_budgets tables if they do not exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS category_budgets (
            category TEXT PRIMARY KEY,
            monthly_limit REAL NOT NULL CHECK (monthly_limit > 0)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            spent_on TEXT NOT NULL,
            payment_mode TEXT NOT NULL DEFAULT 'UPI'
        );

        CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
        CREATE INDEX IF NOT EXISTS idx_expenses_spent_on ON expenses(spent_on);
        """
    )
    conn.commit()


def set_category_budget(conn: sqlite3.Connection, category: str, monthly_limit: float) -> None:
    """Insert or update the monthly budget limit for a category."""
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Unsupported category '{category}'. Choose from {VALID_CATEGORIES}.")
    if monthly_limit <= 0:
        raise ValueError("Monthly budget limit must be greater than 0.")

    conn.execute(
        """
        INSERT INTO category_budgets (category, monthly_limit)
        VALUES (?, ?)
        ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit
        """,
        (category, round(monthly_limit, 2)),
    )
    conn.commit()


def add_expense(
    conn: sqlite3.Connection,
    title: str,
    category: str,
    amount: float,
    spent_on: str,
    payment_mode: str = "UPI",
) -> int:
    """Insert a validated expense record and return its new row ID."""
    if not title or not title.strip():
        raise ValueError("Expense title cannot be empty.")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category '{category}'. Choose from {VALID_CATEGORIES}.")
    if amount <= 0:
        raise ValueError("Expense amount must be greater than 0.")

    cursor = conn.execute(
        """
        INSERT INTO expenses (title, category, amount, spent_on, payment_mode)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title.strip(), category, round(amount, 2), spent_on, payment_mode),
    )
    conn.commit()
    return int(cursor.lastrowid)


def fetch_category_summary(conn: sqlite3.Connection, year_month: str) -> list[dict]:
    """
    Aggregate total spend, transaction count, and budget utilization per category
    for a given YYYY-MM month using LEFT JOIN and GROUP BY.
    """
    rows = conn.execute(
        """
        SELECT
            e.category AS category,
            COUNT(e.id) AS tx_count,
            ROUND(SUM(e.amount), 2) AS total_spent,
            ROUND(AVG(e.amount), 2) AS avg_spent,
            COALESCE(b.monthly_limit, 0.0) AS budget_limit
        FROM expenses e
        LEFT JOIN category_budgets b ON e.category = b.category
        WHERE substr(e.spent_on, 1, 7) = ?
        GROUP BY e.category
        ORDER BY total_spent DESC
        """,
        (year_month,),
    ).fetchall()

    results: list[dict] = []
    for row in rows:
        spent = float(row["total_spent"])
        limit_val = float(row["budget_limit"])
        utilization = round((spent / limit_val) * 100.0, 2) if limit_val > 0 else 0.0
        status = "OK"
        if limit_val > 0 and spent > limit_val:
            status = "OVER_BUDGET"
        elif limit_val > 0 and utilization >= 85.0:
            status = "WARNING_NEAR_LIMIT"

        results.append(
            {
                "category": row["category"],
                "tx_count": int(row["tx_count"]),
                "total_spent": spent,
                "avg_spent": float(row["avg_spent"]),
                "budget_limit": limit_val,
                "utilization_pct": utilization,
                "status": status,
            }
        )
    return results
