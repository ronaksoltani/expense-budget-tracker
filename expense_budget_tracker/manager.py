"""SQLite-backed budget operations."""

from __future__ import annotations

import os
import re
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from .models import Expense, validate_month


class BudgetManager:
    def __init__(self, database: Path | None = None) -> None:
        configured = database or Path(os.getenv("EXPENSE_DB_PATH", "data/expenses.db"))
        self.database = configured.expanduser()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    spent_on TEXT NOT NULL,
                    currency TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_expenses_month_currency
                    ON expenses(spent_on, currency);
                CREATE TABLE IF NOT EXISTS budgets (
                    month TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    PRIMARY KEY (month, currency)
                );
                """
            )

    def add_expense(self, expense: Expense) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO expenses (amount, category, description, spent_on, currency)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    str(expense.amount),
                    expense.category,
                    expense.description,
                    expense.spent_on.isoformat(),
                    expense.currency,
                ),
            )
            return int(cursor.lastrowid)

    def set_budget(self, month: str, amount: Decimal, currency: str) -> None:
        month = validate_month(month)
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Currency must be a three-letter uppercase code.")
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Budget amount must be greater than zero.")
        if amount.as_tuple().exponent < -2 or len(amount.as_tuple().digits) > 12:
            raise ValueError("Budget must have at most 12 digits and two decimal places.")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO budgets (month, currency, amount) VALUES (?, ?, ?)
                   ON CONFLICT(month, currency) DO UPDATE SET amount = excluded.amount""",
                (month, currency, str(amount)),
            )

    def monthly_report(self, month: str, currency: str) -> dict[str, Any]:
        month = validate_month(month)
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Currency must be a three-letter uppercase code.")
        with self._connection() as connection:
            expenses = connection.execute(
                """SELECT amount, category FROM expenses
                   WHERE substr(spent_on, 1, 7) = ? AND currency = ?""",
                (month, currency),
            ).fetchall()
            budget_row = connection.execute(
                "SELECT amount FROM budgets WHERE month = ? AND currency = ?",
                (month, currency),
            ).fetchone()
        category_totals: dict[str, Decimal] = defaultdict(Decimal)
        total = Decimal("0.00")
        for row in expenses:
            amount = Decimal(row["amount"])
            total += amount
            category_totals[row["category"]] += amount
        budget = Decimal(budget_row["amount"]) if budget_row else None
        return {
            "month": month,
            "currency": currency,
            "total": total,
            "budget": budget,
            "remaining": budget - total if budget is not None else None,
            "usage_percent": total / budget * Decimal("100") if budget else None,
            "category_totals": dict(sorted(category_totals.items())),
            "expense_count": len(expenses),
        }

    def list_expenses(self, month: str | None = None, currency: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT spent_on, category, description, amount, currency FROM expenses"
        conditions = []
        values: list[str] = []
        if month:
            conditions.append("substr(spent_on, 1, 7) = ?")
            values.append(validate_month(month))
        if currency:
            conditions.append("currency = ?")
            values.append(currency)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY spent_on DESC, id DESC"
        with self._connection() as connection:
            return connection.execute(query, values).fetchall()
