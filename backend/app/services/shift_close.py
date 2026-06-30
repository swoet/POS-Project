from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


MONEY = Decimal("0.01")


@dataclass(frozen=True)
class TenderLine:
    payment_method: str
    amount: Decimal
    status: str = "completed"


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def reconcile_shift(
    tenders: Iterable[TenderLine],
    counted_cash: Decimal | int | float | str,
    opening_float: Decimal | int | float | str = 0,
) -> dict:
    """Summarize real tender lines and calculate a cash drawer variance."""
    tender_totals: dict[str, Decimal] = {}
    completed_count = 0

    for tender in tenders:
        if tender.status.lower() != "completed":
            continue

        method = tender.payment_method.lower().strip()
        if not method:
            raise ValueError("payment_method is required")
        if tender.amount < 0:
            raise ValueError("tender amount cannot be negative")

        tender_totals[method] = tender_totals.get(method, Decimal("0.00")) + money(tender.amount)
        completed_count += 1

    cash_sales = tender_totals.get("cash", Decimal("0.00"))
    expected_cash = cash_sales + money(opening_float)
    counted = money(counted_cash)
    variance = counted - expected_cash

    return {
        "completed_tenders": completed_count,
        "tender_totals": {key: money(value) for key, value in sorted(tender_totals.items())},
        "expected_cash": money(expected_cash),
        "counted_cash": counted,
        "variance": money(variance),
        "balanced": variance == 0,
    }
