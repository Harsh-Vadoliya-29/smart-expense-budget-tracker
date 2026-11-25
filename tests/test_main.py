"""Unit tests for Smart Expense & Budget Analytics Tracker."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database import add_expense, fetch_category_summary, get_connection, set_category_budget
from tracker import build_monthly_report, detect_high_value_outliers, export_html_dashboard


class TestSmartExpenseTracker(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = get_connection(":memory:")
        set_category_budget(self.conn, "Food", 2000.0)
        set_category_budget(self.conn, "Transport", 1500.0)

    def tearDown(self) -> None:
        self.conn.close()

    def test_add_expense_and_category_summary_over_budget(self) -> None:
        add_expense(self.conn, "Groceries", "Food", 1200.0, "2026-11-05")
        add_expense(self.conn, "Restaurant", "Food", 1100.0, "2026-11-12")
        add_expense(self.conn, "Bus Pass", "Transport", 500.0, "2026-11-02")

        summary = fetch_category_summary(self.conn, "2026-11")
        self.assertEqual(len(summary), 2)
        food = summary[0]
        self.assertEqual(food["category"], "Food")
        self.assertEqual(food["total_spent"], 2300.0)
        self.assertEqual(food["status"], "OVER_BUDGET")

    def test_detect_high_value_outliers(self) -> None:
        add_expense(self.conn, "Snack 1", "Food", 100.0, "2026-11-01")
        add_expense(self.conn, "Snack 2", "Food", 100.0, "2026-11-02")
        add_expense(self.conn, "Big Party Dinner", "Food", 1000.0, "2026-11-03")

        outliers = detect_high_value_outliers(self.conn, "2026-11", multiplier=2.0)
        self.assertEqual(len(outliers), 1)
        self.assertEqual(outliers[0]["title"], "Big Party Dinner")

    def test_validation_rejects_invalid_category_or_negative_amount(self) -> None:
        with self.assertRaises(ValueError):
            add_expense(self.conn, "Bad Category", "Gaming", 500.0, "2026-11-01")
        with self.assertRaises(ValueError):
            add_expense(self.conn, "Negative Amount", "Food", -50.0, "2026-11-01")

    def test_build_monthly_report_and_html_export(self) -> None:
        add_expense(self.conn, "Books", "Education", 850.0, "2026-11-10")
        report = build_monthly_report(self.conn, "2026-11")
        self.assertEqual(report["total_spent"], 850.0)

        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "dashboard.html"
            export_html_dashboard(report, out_file)
            self.assertTrue(out_file.exists())
            self.assertIn("Smart Expense", out_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
