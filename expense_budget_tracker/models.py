"""Validated domain model for an expense record."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Expense(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=2, max_length=200)
    spent_on: date = Field(default_factory=date.today)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


def validate_month(value: str) -> str:
    try:
        year, month = value.split("-", maxsplit=1)
        if len(year) != 4 or not year.isdigit() or len(month) != 2 or not month.isdigit():
            raise ValueError
        if int(year) < 1 or not 1 <= int(month) <= 12:
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError("Month must use YYYY-MM format.") from exc
    return value
