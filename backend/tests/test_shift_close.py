from decimal import Decimal

import pytest

from app.services.shift_close import TenderLine, reconcile_shift


def test_reconcile_shift_calculates_cash_variance():
    result = reconcile_shift(
        [
            TenderLine("cash", Decimal("75.50")),
            TenderLine("card", Decimal("140.00")),
            TenderLine("cash", Decimal("24.50")),
            TenderLine("cash", Decimal("500.00"), status="cancelled"),
        ],
        counted_cash=Decimal("120.00"),
        opening_float=Decimal("20.00"),
    )

    assert result["completed_tenders"] == 3
    assert result["tender_totals"]["cash"] == Decimal("100.00")
    assert result["expected_cash"] == Decimal("120.00")
    assert result["variance"] == Decimal("0.00")
    assert result["balanced"] is True


def test_reconcile_shift_rejects_negative_tenders():
    with pytest.raises(ValueError, match="cannot be negative"):
        reconcile_shift([TenderLine("cash", Decimal("-1.00"))], counted_cash=0)
