# Smart Expense & Budget Analytics Tracker

A Python & SQLite expense analytics tool that tracks monthly category budgets, flags over-budget categories and unusual high-value expenses using SQL queries, and exports an HTML dashboard report.

## Project Structure
- `database.py` — SQLite schema (`expenses` and `category_budgets`), parameterized CRUD functions, and `LEFT JOIN` / `GROUP BY` monthly summary query.
- `tracker.py` — Category outlier detection ($2\times$ category average) and standalone HTML dashboard exporter.
- `tests/test_main.py` — Unit tests using Python's built-in `unittest` module and in-memory SQLite (`:memory:`).

## How to Run

```bash
# Run the sample monthly analytics report
python tracker.py

# Run unit tests
python -m unittest discover -s tests -p "test_*.py" -v
```
