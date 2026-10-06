"""Convert ORM objects into JSON-friendly dictionaries."""
from datetime import date

from app.models import Process, Phase, Validation, Alert


def validation_to_dict(v: Validation | None) -> dict | None:
    if v is None:
        return None
    return {
        "id": v.id,
        "created_at": v.created_at.isoformat(timespec="seconds"),
        "passed": v.passed,
        "score": v.score,
        "risk_probability": v.risk_probability,
        "risk_level": v.risk_level,
        "findings": v.findings,
        "recommendations": v.recommendations,
        "risk_factors": v.risk_factors,
        "summary": v.summary,
    }


def phase_to_dict(phase: Phase, include_detail: bool = True) -> dict:
    data = {
        "id": phase.id,
        "order": phase.order,
        "name": phase.name,
        "description": phase.description,
        "status": phase.status,
        "planned_days": phase.planned_days,
        "start_date": phase.start_date.isoformat() if phase.start_date else None,
        "due_date": phase.due_date.isoformat() if phase.due_date else None,
        "completed_at": phase.completed_at.isoformat() if phase.completed_at else None,
        "rejections": phase.rejections,
        "last_score": phase.last_score,
        "last_risk": phase.last_risk,
        "validations_count": len(phase.validations),
    }
    if include_detail:
        data["requirements"] = phase.requirements
        data["submission"] = phase.submission or {"fields": {}, "documents": {}}
        data["last_validation"] = validation_to_dict(phase.validations[0] if phase.validations else None)
    return data


def alert_to_dict(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "process_id": alert.process_id,
        "process_name": alert.process.name if alert.process else None,
        "phase_id": alert.phase_id,
        "level": alert.level,
        "kind": alert.kind,
        "message": alert.message,
        "created_at": alert.created_at.isoformat(timespec="seconds"),
        "resolved": alert.resolved,
    }


def process_progress(process: Process) -> float:
    approved = sum(1 for p in process.phases if p.status == "approved")
    return round(100 * approved / max(len(process.phases), 1), 1)


def current_phase(process: Process) -> Phase | None:
    return next((p for p in process.phases if p.order == process.current_phase_order), None)


def process_to_dict(process: Process, include_phases: bool = False) -> dict:
    phase = current_phase(process)
    open_alerts = [a for a in process.alerts if not a.resolved]
    data = {
        "id": process.id,
        "name": process.name,
        "description": process.description,
        "template_key": process.template_key,
        "category": process.category,
        "owner": process.owner,
        "start_date": process.start_date.isoformat(),
        "status": process.status,
        "progress": process_progress(process),
        "current_phase": phase.name if phase and process.status != "completed" else None,
        "current_phase_order": process.current_phase_order,
        "total_phases": len(process.phases),
        "current_risk": phase.last_risk if phase and process.status != "completed" else None,
        "open_alerts": len(open_alerts),
        "critical_alerts": sum(1 for a in open_alerts if a.level == "critical"),
        "is_overdue": bool(phase and phase.due_date and phase.status != "approved"
                           and date.today() > phase.due_date),
    }
    if include_phases:
        data["phases"] = [phase_to_dict(p) for p in process.phases]
        data["alerts"] = [alert_to_dict(a) for a in sorted(process.alerts, key=lambda a: a.id, reverse=True)]
    return data
