"""Alert creation with de-duplication and automatic resolution."""
from sqlalchemy.orm import Session

from app.models import Alert

SEVERITY_TO_LEVEL = {"error": "critical", "warning": "warning", "info": "info"}
CATEGORY_TO_KIND = {
    "requirement": "error",
    "document": "error",
    "quality": "error",
    "consistency": "inconsistency",
    "deadline": "delay",
    "risk": "risk",
}


def raise_alert(db: Session, *, process_id: int, phase_id: int | None, code: str,
                level: str, kind: str, message: str) -> Alert:
    """Create an alert unless an identical open one already exists (then refresh it)."""
    existing = (db.query(Alert)
                .filter_by(process_id=process_id, phase_id=phase_id, code=code, resolved=False)
                .first())
    if existing:
        existing.level, existing.message = level, message
        return existing
    alert = Alert(process_id=process_id, phase_id=phase_id, code=code,
                  level=level, kind=kind, message=message)
    db.add(alert)
    return alert


def sync_phase_alerts(db: Session, *, process_id: int, phase_id: int, findings: list[dict],
                      risk_level: str, risk_probability: float) -> None:
    """Open alerts for current problems and resolve the ones that were fixed."""
    active_codes = set()

    for f in findings:
        if f["severity"] == "info" and f["category"] != "deadline":
            continue
        active_codes.add(f["code"])
        raise_alert(db, process_id=process_id, phase_id=phase_id, code=f["code"],
                    level=f.get("alert_level") or SEVERITY_TO_LEVEL[f["severity"]], kind=CATEGORY_TO_KIND.get(f["category"], "error"),
                    message=f["message"])

    if risk_level in ("medium", "high"):
        active_codes.add("risk:delay")
        raise_alert(db, process_id=process_id, phase_id=phase_id, code="risk:delay",
                    level="critical" if risk_level == "high" else "warning", kind="risk",
                    message=f"La IA estima un riesgo {'alto' if risk_level == 'high' else 'medio'} "
                            f"de retraso ({risk_probability * 100:.0f}%).")

    open_alerts = db.query(Alert).filter_by(process_id=process_id, phase_id=phase_id, resolved=False).all()
    for alert in open_alerts:
        if alert.code not in active_codes:
            alert.resolved = True


def resolve_phase_alerts(db: Session, phase_id: int) -> None:
    for alert in db.query(Alert).filter_by(phase_id=phase_id, resolved=False).all():
        alert.resolved = True
