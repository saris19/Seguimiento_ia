"""Templates catalog, dashboard, alerts and AI model information."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.risk_model import get_model
from app.catalog import list_templates
from app.database import get_db
from app.models import Alert, Process
from app.services.monitor_service import scan_deadlines
from app.services.serializers import alert_to_dict, process_to_dict

router = APIRouter(prefix="/api", tags=["General"])


@router.get("/templates")
def templates():
    return list_templates()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    scan_deadlines(db)
    processes = db.query(Process).all()
    data = [process_to_dict(p) for p in processes]
    open_alerts = db.query(Alert).filter_by(resolved=False).order_by(Alert.id.desc()).all()
    at_risk = sorted([p for p in data if p["status"] != "completed" and (p["current_risk"] or 0) >= 0.4],
                     key=lambda p: p["current_risk"], reverse=True)
    return {
        "kpis": {
            "total": len(data),
            "active": sum(1 for p in data if p["status"] == "active"),
            "blocked": sum(1 for p in data if p["status"] == "blocked"),
            "completed": sum(1 for p in data if p["status"] == "completed"),
            "overdue": sum(1 for p in data if p["is_overdue"] and p["status"] != "completed"),
            "open_alerts": len(open_alerts),
            "critical_alerts": sum(1 for a in open_alerts if a.level == "critical"),
        },
        "by_category": {c: sum(1 for p in data if p["category"] == c)
                        for c in ("academic", "administrative", "business")},
        "at_risk": at_risk[:5],
        "recent_alerts": [alert_to_dict(a) for a in open_alerts[:10]],
    }


@router.get("/alerts")
def alerts(resolved: bool = False, db: Session = Depends(get_db)):
    rows = db.query(Alert).filter_by(resolved=resolved).order_by(Alert.id.desc()).limit(200).all()
    return [alert_to_dict(a) for a in rows]


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alerta no encontrada.")
    alert.resolved = True
    db.commit()
    return alert_to_dict(alert)


@router.get("/ai/model")
def model_info():
    return get_model().metrics
