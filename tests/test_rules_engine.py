"""Unit tests for the deterministic part of the AI supervisor."""
from datetime import date

from app.ai.rules_engine import evaluate_phase, check_deadline
from app.ai.risk_model import get_model
from app.ai.supervisor import supervise_phase
from app.catalog import get_template

PURCHASE = get_template("admin_purchase")
QUOTES_PHASE = PURCHASE["phases"][1]
PREVIOUS = {1: {"budget": 45_000_000}}
DOCS = {"quotes_doc": {"filename": "cuadro.pdf", "size": 1200}}


def _evaluate(fields, documents=DOCS):
    return evaluate_phase(QUOTES_PHASE["requirements"], QUOTES_PHASE["rules"],
                          {"fields": fields, "documents": documents}, PREVIOUS, 2, None, None)


def test_complete_phase_has_no_findings():
    result = _evaluate({"quotes_count": 3, "supplier": "Proveedor SAS", "quoted_amount": 40_000_000})
    assert result.findings == []
    assert result.completion_ratio == 1.0


def test_missing_document_is_blocking():
    result = _evaluate({"quotes_count": 3, "supplier": "Proveedor SAS", "quoted_amount": 1}, documents={})
    assert result.has_errors
    assert any(f.code == "missing_doc:quotes_doc" for f in result.findings)


def test_cross_phase_inconsistency_detected():
    result = _evaluate({"quotes_count": 3, "supplier": "Proveedor SAS", "quoted_amount": 50_000_000})
    assert any(f.category == "consistency" and f.field == "quoted_amount" for f in result.findings)


def test_wrong_extension_rejected():
    result = _evaluate({"quotes_count": 3, "supplier": "Proveedor SAS", "quoted_amount": 1},
                       documents={"quotes_doc": {"filename": "cuadro.exe", "size": 10}})
    assert any(f.code == "bad_ext:quotes_doc" for f in result.findings)


def test_placeholder_text_generates_warning():
    phase = PURCHASE["phases"][0]
    result = evaluate_phase(phase["requirements"], phase["rules"],
                            {"fields": {"need": "Lorem ipsum dolor sit amet " * 4, "area": "TI", "budget": 10}},
                            {}, 1, None, None)
    assert any(f.category == "quality" for f in result.findings)


def test_deadline_overdue_and_near():
    start, due = date(2026, 1, 1), date(2026, 1, 11)
    assert check_deadline(start, due, date(2026, 1, 25)).alert_level == "critical"
    assert check_deadline(start, due, date(2026, 1, 13)).alert_level == "warning"
    assert check_deadline(start, due, date(2026, 1, 25)).severity == "warning"   # delays never block
    assert check_deadline(start, due, date(2026, 1, 10)).code == "deadline:near"
    assert check_deadline(start, due, date(2026, 1, 3)) is None


def test_risk_model_quality_and_monotonicity():
    model = get_model()
    assert model.metrics["roc_auc"] > 0.75
    base = {"completion_ratio": 0.9, "time_ratio": 0.3, "rejections": 0,
            "prev_delay_days": 0, "phase_position": 0.5, "error_count": 0}
    late = {**base, "time_ratio": 1.8, "rejections": 3, "error_count": 4, "completion_ratio": 0.3}
    assert model.predict(late).probability > model.predict(base).probability
    assert model.predict(late).level == "high"


def test_supervisor_blocks_when_errors():
    result = supervise_phase(requirements=QUOTES_PHASE["requirements"], rules=QUOTES_PHASE["rules"],
                             submission={"fields": {"quotes_count": 1}, "documents": {}},
                             previous_fields=PREVIOUS, phase_order=2, total_phases=4,
                             start=date.today(), due=None, planned_days=10, rejections=0, prev_delay_days=0)
    assert not result.passed
    assert result.recommendations
