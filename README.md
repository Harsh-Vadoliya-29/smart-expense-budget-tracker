# Smart Expense & Budget Analytics Tracker

A Python & SQLite expense analytics application that tracks monthly category budgets, flags over-budget categories and unusual high-value expenses using SQL queries, and provides both a saved HTML report (`dashboard.html`) and an interactive local Web GUI (`python tracker.py --gui`).

## Project Structure
- `database.py` — SQLite schema (`expenses` and `category_budgets`), parameterized CRUD functions, and `LEFT JOIN` / `GROUP BY` monthly summary query.
- `tracker.py` — Category outlier detection ($2\times$ category average), HTML dashboard generator, and built-in local Web GUI server (`http.server`).
- `tests/test_main.py` — Unit tests using Python's built-in `unittest` module and in-memory SQLite (`:memory:`).

## How to Run

```bash
# 1. Run CLI analytics + generate dashboard.html
python tracker.py

# 2. Launch the interactive Web GUI in your browser (http://localhost:8000)
python tracker.py --gui

# 3. Run unit tests
python -m unittest discover -s tests -p "test_*.py" -v
```
