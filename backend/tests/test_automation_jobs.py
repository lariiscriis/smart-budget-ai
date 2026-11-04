import pytest

from app.automation_worker import validate_workflow_result
from app.schemas import ExpenseCreate
from app.services.automation_jobs import imported_periods


def expense(day: str) -> ExpenseCreate:
    return ExpenseCreate(
        category_id=1,
        description="Despesa fictícia",
        expense_date=day,
        amount="10.00",
    )


def test_periods_are_unique_and_sorted():
    result = imported_periods([
        expense("2026-12-10"),
        expense("2026-11-05"),
        expense("2026-12-20"),
    ])

    assert result == [(2026, 11), (2026, 12)]


def test_empty_import_has_no_periods():
    assert imported_periods([]) == []


def workflow_result() -> dict:
    return {
        "summary": {
            "year": 2026,
            "month": 12,
            "currency": "BRL",
            "planned": "1000.00",
            "actual": "250.00",
            "balance": "750.00",
            "utilization_percentage": "25.00",
        },
        "alerts": {
            "year": 2026,
            "month": 12,
            "rules_version": "1.0",
            "count": 0,
            "alerts": [],
        },
    }


def test_accepts_expected_workflow_result():
    result = validate_workflow_result(workflow_result(), 2026, 12)
    assert result.summary.month == 12


def test_rejects_other_period():
    data = workflow_result()
    data["summary"]["month"] = 11

    with pytest.raises(ValueError, match="outro período"):
        validate_workflow_result(data, 2026, 12)


def test_rejects_inconsistent_alert_count():
    data = workflow_result()
    data["alerts"]["count"] = 1

    with pytest.raises(ValueError, match="contagem"):
        validate_workflow_result(data, 2026, 12)