"""Business logic: process lifecycle, submissions, AI validation and phase advance."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.ai.supervisor import supervise_phase
from app.catalog import get_template
from app.config import UPLOAD_DIR
from app.models import Process, Phase, Validation
from app.services.alert_service import sync_phase_alerts, resolve_phase_alerts, raise_alert


class ProcessError(Exception):
    """Business-rule violation (mapped to HTTP 400/409 by the API)."""


# --------------------------------------------------------------------------- #
# Creation
# --------------------------------------------------------------------------- #
def create_process(db: Session, *, template_key: str, name: str, owner: str,
                   description: str = "", start_date: date | None = None) -> Process:
    template = get_template(template_key)
    if not template:
        raise ProcessError(f"La plantilla «{template_key}» no existe.")

    start_date = start_date or date.today()
    process = Process(name=name, owner=owner, description=description, template_key=template_key,
                      category=template["category"], start_date=start_date, current_phase_order=1)

    for order, phase_def in enumerate(template["phases"], start=1):
        phase = Phase(order=order, name=phase_def["name"], description=phase_def["description"],
                      planned_days=phase_def["planned_days"], requirements=phase_def["requirements"],
                      rules=phase_def["rules"], submission={"fields": {}, "documents": {}})
        if order == 1:
            phase.status = "in_progress"
            phase.start_date = start_date
            phase.due_date = start_date + timedelta(days=phase_def["planned_days"])
        process.phases.append(phase)

    db.add(process)
    db.commit()
    db.refresh(process)
    return process


# --------------------------------------------------------------------------- #
# Submissions
# --------------------------------------------------------------------------- #
def _ensure_editable(phase: Phase):
    if phase.status not in ("in_progress", "blocked"):
        raise ProcessError("Solo se puede modificar la fase activa del proceso.")


def save_fields(db: Session, phase: Phase, fields: dict) -> Phase:
    _ensure_editable(phase)
    allowed = {r["key"]: r for r in phase.requirements if r["type"] != "document"}
    submission = dict(phase.submission or {})
    current = dict(submission.get("fields", {}))
    for key, value in fields.items():
        if key not in allowed:
            continue
        if allowed[key]["type"] == "checklist":
            value = bool(value)
        current[key] = value
    submission["fields"] = current
    submission.setdefault("documents", {})
    phase.submission = submission   # reassign so SQLAlchemy detects the JSON change
    db.commit()
    return phase


def save_document(db: Session, phase: Phase, key: str, filename: str, content: bytes) -> Phase:
    _ensure_editable(phase)
    if not any(r["key"] == key and r["type"] == "document" for r in phase.requirements):
        raise ProcessError(f"«{key}» no es un documento requerido en esta fase.")

    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120] or "archivo"
    stored_name = f"{phase.process_id}_{phase.id}_{key}_{uuid.uuid4().hex[:8]}_{safe_name}"
    (UPLOAD_DIR / stored_name).write_bytes(content)

    submission = dict(phase.submission or {})
    documents = dict(submission.get("documents", {}))
    documents[key] = {"filename": filename, "stored_name": stored_name, "size": len(content),
                      "uploaded_at": datetime.now().isoformat(timespec="seconds")}
    submission["documents"] = documents
    submission.setdefault("fields", {})
    phase.submission = submission
    db.commit()
    return phase


# --------------------------------------------------------------------------- #
# AI validation
# --------------------------------------------------------------------------- #
def _previous_fields(process: Process, order: int) -> dict[int, dict]:
    return {p.order: (p.submission or {}).get("fields", {}) for p in process.phases if p.order < order}


def accumulated_delay(process: Process, order: int) -> int:
    total = 0
    for p in process.phases:
        if p.order < order and p.completed_at and p.due_date:
            total += max(0, (p.completed_at - p.due_date).days)
    return total


def validate_phase(db: Session, phase: Phase, today: date | None = None) -> Validation:
    """Run the AI supervisor on a phase, store the result and sync alerts."""
    today = today or date.today()
    if phase.status not in ("in_progress", "blocked"):
        raise ProcessError("Solo se puede validar la fase activa.")
    process = phase.process

    result = supervise_phase(
        requirements=phase.requirements, rules=phase.rules, submission=phase.submission or {},
        previous_fields=_previous_fields(process, phase.order), phase_order=phase.order,
        total_phases=len(process.phases), start=phase.start_date, due=phase.due_date,
        planned_days=phase.planned_days, rejections=phase.rejections,
        prev_delay_days=accumulated_delay(process, phase.order), today=today,
    )
    findings = [f.to_dict() for f in result.findings]

    validation = Validation(
        phase_id=phase.id, passed=result.passed, score=result.score,
        risk_probability=result.risk.probability, risk_level=result.risk.level,
        findings=findings, recommendations=result.recommendations,
        risk_factors=result.risk.factors, summary=result.summary,
    )
    db.add(validation)

    phase.last_score = result.score
    phase.last_risk = result.risk.probability
    if not result.passed:
        phase.rejections += 1

    sync_phase_alerts(db, process_id=process.id, phase_id=phase.id, findings=findings,
                      risk_level=result.risk.level, risk_probability=result.risk.probability)
    db.commit()
    db.refresh(validation)
    return validation


# --------------------------------------------------------------------------- #
# Phase advance (AI gate)
# --------------------------------------------------------------------------- #
def advance_phase(db: Session, phase: Phase, today: date | None = None) -> tuple[Validation, Process]:
    """
    The AI gate: the phase is validated again at the moment of advancing.
    If it does not pass, the phase becomes *blocked* and the process cannot continue.
    """
    today = today or date.today()
    validation = validate_phase(db, phase, today)
    process = phase.process

    if not validation.passed:
        phase.status = "blocked"
        process.status = "blocked"
        db.commit()
        return validation, process

    phase.status = "approved"
    phase.completed_at = today
    resolve_phase_alerts(db, phase.id)

    next_phase = next((p for p in process.phases if p.order == phase.order + 1), None)
    if next_phase:
        next_phase.status = "in_progress"
        next_phase.start_date = today
        next_phase.due_date = today + timedelta(days=next_phase.planned_days)
        process.current_phase_order = next_phase.order
        process.status = "active"
    else:
        process.status = "completed"
        process.completed_at = datetime.now()
        done = raise_alert(db, process_id=process.id, phase_id=None, code="process:completed", level="info",
                           kind="status", message="Proceso finalizado: todas las fases fueron validadas por la IA.")
        done.resolved = True   # informative record, not an open alert
    db.commit()
    db.refresh(process)
    return validation, process
