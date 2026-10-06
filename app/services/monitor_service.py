"""
Continuous monitor: detects delays even when nobody runs a validation.
It is executed when the dashboard or the process list is requested.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.config import DEADLINE_WARNING_RATIO
from app.models import Process
from app.services.alert_service import raise_alert


def scan_deadlines(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    raised = 0
    for process in db.query(Process).filter(Process.status != "completed").all():
        phase = next((p for p in process.phases if p.order == process.current_phase_order), None)
        if not phase or not phase.due_date or not phase.start_date:
            continue
        if today > phase.due_date:
            days_late = (today - phase.due_date).days
            raise_alert(db, process_id=process.id, phase_id=phase.id, code="deadline:overdue",
                        level="critical" if days_late > 7 else "warning", kind="delay",
                        message=f"Fase «{phase.name}» vencida hace {days_late} día(s).")
            raised += 1
        else:
            total = max((phase.due_date - phase.start_date).days, 1)
            if (today - phase.start_date).days / total >= DEADLINE_WARNING_RATIO:
                raise_alert(db, process_id=process.id, phase_id=phase.id, code="deadline:near",
                            level="info", kind="delay",
                            message=f"Fase «{phase.name}» próxima a vencer ({phase.due_date.isoformat()}).")
                raised += 1
    db.commit()
    return raised
