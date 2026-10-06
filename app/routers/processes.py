"""Endpoints for processes and their reports."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Process
from app.schemas import ProcessCreate
from app.services import process_service
from app.services.monitor_service import scan_deadlines
from app.services.report_service import build_report, render_report_html
from app.services.serializers import process_to_dict

router = APIRouter(prefix="/api/processes", tags=["Procesos"])


def _get_process(db: Session, process_id: int) -> Process:
    process = db.get(Process, process_id)
    if not process:
        raise HTTPException(404, "Proceso no encontrado.")
    return process


@router.get("")
def list_processes(status: str | None = None, category: str | None = None, db: Session = Depends(get_db)):
    scan_deadlines(db)
    query = db.query(Process)
    if status:
        query = query.filter(Process.status == status)
    if category:
        query = query.filter(Process.category == category)
    return [process_to_dict(p) for p in query.order_by(Process.id.desc()).all()]


@router.post("", status_code=201)
def create_process(payload: ProcessCreate, db: Session = Depends(get_db)):
    try:
        process = process_service.create_process(db, **payload.model_dump())
    except process_service.ProcessError as exc:
        raise HTTPException(400, str(exc))
    return process_to_dict(process, include_phases=True)


@router.get("/{process_id}")
def get_process(process_id: int, db: Session = Depends(get_db)):
    return process_to_dict(_get_process(db, process_id), include_phases=True)


@router.delete("/{process_id}", status_code=204)
def delete_process(process_id: int, db: Session = Depends(get_db)):
    db.delete(_get_process(db, process_id))
    db.commit()


@router.get("/{process_id}/report")
def get_report(process_id: int, db: Session = Depends(get_db)):
    return build_report(_get_process(db, process_id))


@router.get("/{process_id}/report.html", response_class=HTMLResponse)
def get_report_html(process_id: int, db: Session = Depends(get_db)):
    return render_report_html(build_report(_get_process(db, process_id)))
