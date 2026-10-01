"""Command-line interface for expenses, budgets, and monthly summaries."""

from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation

import plotext as plt
from pydantic import ValidationError

from .manager import BudgetManager
from .models import Expense, validate_month


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Track expenses and monthly budgets locally.")
    commands = result.add_subparsers(dest="command", required=True)

    add = commands.add_parser("add", help="Record an expense")
    add.add_argument("--amount", required=True)
    add.add_argument("--category", required=True)
    add.add_argument("--description", required=True)
    add.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD")
    add.add_argument("--currency", default="USD", help="Three-letter currency code")

    budget = commands.add_parser("budget", help="Set the budget for one month")
    budget.add_argument("--month", required=True, help="YYYY-MM")
    budget.add_argument("--amount", required=True)
    budget.add_argument("--currency", default="USD")

    report = commands.add_parser("report", help="Show a monthly spending summary")
    report.add_argument("--month", default=date.today().strftime("%Y-%m"))
    report.add_argument("--currency", default="USD")
    report.add_argument("--no-chart", action="store_true")

    listing = commands.add_parser("list", help="List saved expenses")
    listing.add_argument("--month")
    listing.add_argument("--currency")
    return result


def draw_chart(report: dict[str, object]) -> None:
    categories = report["category_totals"]
    if not categories:
        print("No expenses to chart for this month.")
        return
    plt.clear_figure()
    plt.bar(list(categories.keys()), [float(value) for value in categories.values()])
    plt.title(f"Spending by category · {report['month']}")
    plt.xlabel(str(report["currency"]))
    plt.show()


def main() -> int:
    args = parser().parse_args()
    manager = BudgetManager()
    try:
        if args.command == "add":
            expense = Expense(
                amount=Decimal(args.amount),
                category=args.category,
                description=args.description,
                spent_on=date.fromisoformat(args.date),
                currency=args.currency.upper(),
            )
            identifier = manager.add_expense(expense)
            print(f"Saved expense #{identifier}: {expense.currency} {expense.amount} · {expense.category}")
        elif args.command == "budget":
            month = validate_month(args.month)
            amount = Decimal(args.amount)
            manager.set_budget(month, amount, args.currency.upper())
            print(f"Budget set: {month} · {args.currency.upper()} {amount:.2f}")
        elif args.command == "report":
            summary = manager.monthly_report(args.month, args.currency.upper())
            print(f"Monthly report · {summary['month']} · {summary['currency']}")
            print(f"Transactions: {summary['expense_count']}")
            print(f"Spent: {summary['currency']} {summary['total']:.2f}")
            if summary["budget"] is None:
                print("Budget: not set")
            else:
                print(f"Budget: {summary['currency']} {summary['budget']:.2f}")
                print(f"Remaining: {summary['currency']} {summary['remaining']:.2f}")
                if summary["usage_percent"] is not None:
                    print(f"Budget used: {summary['usage_percent']:.1f}%")
                if summary["budget"] and summary["total"] > summary["budget"]:
                    print("Status: over budget")
            for category, amount in summary["category_totals"].items():
                print(f"  {category}: {summary['currency']} {amount:.2f}")
            if not args.no_chart:
                draw_chart(summary)
        else:
            rows = manager.list_expenses(args.month, args.currency.upper() if args.currency else None)
            for row in rows:
                print(
                    f"{row['spent_on']}  {row['currency']} {Decimal(row['amount']):.2f}  "
                    f"{row['category']}: {row['description']}"
                )
            if not rows:
                print("No expenses found.")
    except (ValidationError, ValueError, InvalidOperation) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
