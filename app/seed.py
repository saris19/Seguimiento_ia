"""Demo data: realistic processes in different states to showcase the platform."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Process
from app.services import process_service as ps

PDF = b"%PDF-1.4\n% documento de demostracion\n"


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _phase(process: Process, order: int):
    return next(p for p in process.phases if p.order == order)


def seed_demo_data(db: Session) -> None:
    if db.query(Process).count() > 0:
        return
    today = date.today()

    # 1) Academic thesis: two phases done (one late), development in progress with gaps
    p1 = ps.create_process(db, template_key="academic_thesis", name="Plataforma de tutorías con IA",
                           owner="Laura Gómez", description="Trabajo de grado de Ingeniería de Software.",
                           start_date=today - timedelta(days=50))
    ph = _phase(p1, 1)
    ps.save_fields(db, ph, {
        "title": "Plataforma web de tutorías personalizadas apoyada en IA",
        "problem": "Los estudiantes de primeros semestres presentan altos índices de reprobación en cursos de "
                   "programación y no cuentan con acompañamiento personalizado fuera del aula de clase.",
        "advisor": "Ing. Carlos Ruiz", "start_date": _d(-50), "end_date": _d(120), "format_ok": True})
    ps.save_document(db, ph, "proposal_doc", "anteproyecto.pdf", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=37))
    ph = _phase(p1, 2)
    ps.save_fields(db, ph, {"decision": "Aprobado con ajustes", "approval_date": _d(-24), "adjustments_done": True})
    ps.save_document(db, ph, "committee_doc", "acta_comite_014.pdf", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=23))
    ph = _phase(p1, 3)
    ps.save_fields(db, ph, {"progress": 60, "progress_report": "Avance del módulo de tutorías. Pendiente por definir "
                                                                "la integración del motor de recomendaciones.",
                            "advisor_review": False})
    ps.validate_phase(db, ph)

    # 2) Administrative purchase: quotations overdue and inconsistent → blocked by the AI
    p2 = ps.create_process(db, template_key="admin_purchase", name="Compra de equipos de laboratorio",
                           owner="Andrés Muñoz", description="Adquisición de 15 computadores para sala de redes.",
                           start_date=today - timedelta(days=26))
    ph = _phase(p2, 1)
    ps.save_fields(db, ph, {"need": "Renovación de 15 equipos de cómputo de la sala de redes que superan "
                                    "los 8 años de uso y no soportan el software actual.",
                            "area": "Facultad de Ingeniería", "budget": 45000000})
    ps.save_document(db, ph, "request_doc", "solicitud_compra.xlsx", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=22))
    ph = _phase(p2, 2)
    ps.save_fields(db, ph, {"quotes_count": 2, "supplier": "TecnoAndina S.A.S.", "quoted_amount": 51200000})
    ps.save_document(db, ph, "quotes_doc", "cuadro_comparativo.pdf", PDF)
    ps.advance_phase(db, ph)   # the AI gate rejects it and blocks the process

    # 3) Business project fully completed
    p3 = ps.create_process(db, template_key="business_project", name="Implementación de CRM comercial",
                           owner="Mariana Torres", description="Adopción de CRM para el equipo de ventas.",
                           start_date=today - timedelta(days=95))
    ph = _phase(p3, 1)
    ps.save_fields(db, ph, {"objective": "Centralizar la gestión de clientes y oportunidades comerciales para "
                                         "mejorar la tasa de conversión del equipo de ventas.",
                            "sponsor": "Gerencia Comercial", "budget": 80000000,
                            "start_date": _d(-95), "end_date": _d(-5)})
    ps.save_document(db, ph, "charter_doc", "acta_constitucion.pdf", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=89))
    ph = _phase(p3, 2)
    ps.save_fields(db, ph, {"milestones": 5, "plan_approved": True,
                            "risks": "Resistencia al cambio del equipo, calidad de los datos migrados y "
                                     "disponibilidad del proveedor de integración."})
    ps.save_document(db, ph, "schedule_doc", "cronograma.xlsx", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=76))
    ph = _phase(p3, 3)
    ps.save_fields(db, ph, {"progress": 100, "spent": 74500000,
                            "status_report": "CRM configurado, datos migrados y 32 usuarios capacitados. "
                                             "Integración con facturación electrónica operativa."})
    ps.save_document(db, ph, "deliverables_doc", "entregables.pdf", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=14))
    ph = _phase(p3, 4)
    ps.save_fields(db, ph, {"lessons": "La capacitación temprana redujo la resistencia al cambio; la limpieza "
                                       "de datos debe planearse antes de la migración.",
                            "closing_date": _d(-8), "client_ok": True})
    ps.save_document(db, ph, "closing_doc", "acta_cierre.pdf", PDF)
    ps.advance_phase(db, ph, today - timedelta(days=8))

    # 4) Business project just started (empty)
    ps.create_process(db, template_key="business_project", name="Lanzamiento de app móvil de pedidos",
                      owner="Sergio Paz", description="Nueva app para pedidos a domicilio.",
                      start_date=today - timedelta(days=2))
