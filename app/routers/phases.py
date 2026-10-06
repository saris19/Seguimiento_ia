"""Endpoints for phase submissions, AI validation and advance."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_BYTES
from app.database import get_db
from app.models import Phase
from app.schemas import SubmissionUpdate
from app.services import process_service
from app.services.serializers import phase_to_dict, validation_to_dict, process_to_dict

router = APIRouter(prefix="/api/phases", tags=["Fases"])


def _get_phase(db: Session, phase_id: int) -> Phase:
    phase = db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, "Fase no encontrada.")
    return phase


@router.get("/{phase_id}")
def get_phase(phase_id: int, db: Session = Depends(get_db)):
    return phase_to_dict(_get_phase(db, phase_id))


@router.get("/{phase_id}/validations")
def list_validations(phase_id: int, db: Session = Depends(get_db)):
    return [validation_to_dict(v) for v in _get_phase(db, phase_id).validations]


@router.put("/{phase_id}/submission")
def save_submission(phase_id: int, payload: SubmissionUpdate, db: Session = Depends(get_db)):
    try:
        phase = process_service.save_fields(db, _get_phase(db, phase_id), payload.fields)
    except process_service.ProcessError as exc:
        raise HTTPException(409, str(exc))
    return phase_to_dict(phase)


@router.post("/{phase_id}/documents")
async def upload_document(phase_id: int, key: str = Form(...), file: UploadFile = File(...),
                          db: Session = Depends(get_db)):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera el tamaño máximo permitido (10 MB).")
    try:
        phase = process_service.save_document(db, _get_phase(db, phase_id), key, file.filename or "archivo", content)
    except process_service.ProcessError as exc:
        raise HTTPException(409, str(exc))
    return phase_to_dict(phase)


@router.post("/{phase_id}/validate")
def validate(phase_id: int, db: Session = Depends(get_db)):
    try:
        validation = process_service.validate_phase(db, _get_phase(db, phase_id))
    except process_service.ProcessError as exc:
        raise HTTPException(409, str(exc))
    return validation_to_dict(validation)


@router.post("/{phase_id}/advance")
def advance(phase_id: int, db: Session = Depends(get_db)):
    try:
        validation, process = process_service.advance_phase(db, _get_phase(db, phase_id))
    except process_service.ProcessError as exc:
        raise HTTPException(409, str(exc))
    return {"advanced": validation.passed, "validation": validation_to_dict(validation),
            "process": process_to_dict(process, include_phases=True)}
