"""
Process templates catalog.

Each template defines the phases a process goes through, the requirements the
AI supervisor checks in each phase and the consistency rules between fields
(even across phases, using the "phase_order.field_key" reference syntax).

Requirement types: text | number | date | select | checklist | document
Rule types:
  - date_order:   field `first` must be <= field `second`
  - max_ref:      numeric `field` must be <= referenced value `ref`
  - equals_ref:   numeric `field` must equal referenced value `ref`
  - min_value:    numeric `field` must be >= `value`
  - forbidden_value: `field` must not take the value `value`
  - date_after_ref: date `field` must be >= referenced date `ref`
"""

TEMPLATES: dict[str, dict] = {
    "academic_thesis": {
        "key": "academic_thesis",
        "name": "Proyecto de grado",
        "category": "academic",
        "description": "Seguimiento de un trabajo de grado desde la propuesta hasta la sustentación.",
        "phases": [
            {
                "name": "Propuesta",
                "description": "Registro del anteproyecto y su planteamiento del problema.",
                "planned_days": 15,
                "requirements": [
                    {"key": "title", "label": "Título del proyecto", "type": "text", "required": True, "min_length": 15},
                    {"key": "problem", "label": "Planteamiento del problema", "type": "text", "required": True, "min_length": 120},
                    {"key": "advisor", "label": "Director / asesor", "type": "text", "required": True, "min_length": 5},
                    {"key": "start_date", "label": "Fecha de inicio planeada", "type": "date", "required": True},
                    {"key": "end_date", "label": "Fecha de finalización planeada", "type": "date", "required": True},
                    {"key": "proposal_doc", "label": "Documento del anteproyecto", "type": "document", "required": True, "extensions": [".pdf", ".docx"]},
                    {"key": "format_ok", "label": "Cumple el formato institucional", "type": "checklist", "required": True},
                ],
                "rules": [
                    {"type": "date_order", "first": "start_date", "second": "end_date",
                     "message": "La fecha de inicio es posterior a la fecha de finalización."},
                ],
            },
            {
                "name": "Aprobación del comité",
                "description": "Evaluación de la propuesta por el comité curricular.",
                "planned_days": 10,
                "requirements": [
                    {"key": "decision", "label": "Decisión del comité", "type": "select", "required": True,
                     "options": ["Aprobado", "Aprobado con ajustes", "No aprobado"]},
                    {"key": "approval_date", "label": "Fecha del acta", "type": "date", "required": True},
                    {"key": "committee_doc", "label": "Acta del comité", "type": "document", "required": True, "extensions": [".pdf"]},
                    {"key": "adjustments_done", "label": "Ajustes solicitados atendidos", "type": "checklist", "required": True},
                ],
                "rules": [
                    {"type": "forbidden_value", "field": "decision", "value": "No aprobado",
                     "message": "La propuesta no fue aprobada: el proceso no puede continuar a desarrollo."},
                    {"type": "date_after_ref", "field": "approval_date", "ref": "1.start_date",
                     "message": "El acta tiene fecha anterior al inicio del proyecto."},
                ],
            },
            {
                "name": "Desarrollo",
                "description": "Ejecución del proyecto y entregas de avance.",
                "planned_days": 90,
                "requirements": [
                    {"key": "progress", "label": "Porcentaje de avance", "type": "number", "required": True, "min": 0, "max": 100},
                    {"key": "progress_report", "label": "Informe de avance", "type": "text", "required": True, "min_length": 80},
                    {"key": "progress_doc", "label": "Documento de avance", "type": "document", "required": True, "extensions": [".pdf", ".docx"]},
                    {"key": "advisor_review", "label": "Revisado por el director", "type": "checklist", "required": True},
                ],
                "rules": [
                    {"type": "min_value", "field": "progress", "value": 100,
                     "message": "El avance reportado es menor al 100%; la fase de desarrollo no puede cerrarse."},
                ],
            },
            {
                "name": "Sustentación",
                "description": "Defensa del proyecto ante jurados y cierre.",
                "planned_days": 20,
                "requirements": [
                    {"key": "defense_date", "label": "Fecha de sustentación", "type": "date", "required": True},
                    {"key": "jury", "label": "Jurados", "type": "text", "required": True, "min_length": 10},
                    {"key": "grade", "label": "Calificación (0 – 5)", "type": "number", "required": True, "min": 0, "max": 5},
                    {"key": "final_doc", "label": "Documento final", "type": "document", "required": True, "extensions": [".pdf"]},
                ],
                "rules": [
                    {"type": "date_after_ref", "field": "defense_date", "ref": "2.approval_date",
                     "message": "La sustentación tiene fecha anterior a la aprobación del comité."},
                    {"type": "min_value", "field": "grade", "value": 3.0,
                     "message": "La calificación es inferior a 3.0 (no aprobatoria)."},
                ],
            },
        ],
    },
    "admin_purchase": {
        "key": "admin_purchase",
        "name": "Compra / contratación",
        "category": "administrative",
        "description": "Proceso administrativo de adquisición de bienes o servicios.",
        "phases": [
            {
                "name": "Solicitud",
                "description": "Necesidad, justificación y presupuesto estimado.",
                "planned_days": 5,
                "requirements": [
                    {"key": "need", "label": "Descripción de la necesidad", "type": "text", "required": True, "min_length": 60},
                    {"key": "area", "label": "Área solicitante", "type": "text", "required": True, "min_length": 3},
                    {"key": "budget", "label": "Presupuesto estimado (COP)", "type": "number", "required": True, "min": 1},
                    {"key": "request_doc", "label": "Formato de solicitud", "type": "document", "required": True, "extensions": [".pdf", ".docx", ".xlsx"]},
                ],
                "rules": [],
            },
            {
                "name": "Cotizaciones",
                "description": "Comparación de proveedores.",
                "planned_days": 10,
                "requirements": [
                    {"key": "quotes_count", "label": "Número de cotizaciones", "type": "number", "required": True, "min": 0},
                    {"key": "supplier", "label": "Proveedor seleccionado", "type": "text", "required": True, "min_length": 3},
                    {"key": "quoted_amount", "label": "Valor cotizado seleccionado (COP)", "type": "number", "required": True, "min": 1},
                    {"key": "quotes_doc", "label": "Cuadro comparativo", "type": "document", "required": True, "extensions": [".pdf", ".xlsx"]},
                ],
                "rules": [
                    {"type": "min_value", "field": "quotes_count", "value": 3,
                     "message": "Se requieren al menos 3 cotizaciones para garantizar selección objetiva."},
                    {"type": "max_ref", "field": "quoted_amount", "ref": "1.budget",
                     "message": "El valor cotizado supera el presupuesto estimado en la solicitud."},
                ],
            },
            {
                "name": "Aprobación",
                "description": "Autorización del gasto por el ordenador.",
                "planned_days": 5,
                "requirements": [
                    {"key": "approver", "label": "Aprobado por", "type": "text", "required": True, "min_length": 5},
                    {"key": "approved_amount", "label": "Valor aprobado (COP)", "type": "number", "required": True, "min": 1},
                    {"key": "approval_date", "label": "Fecha de aprobación", "type": "date", "required": True},
                    {"key": "approval_doc", "label": "Documento de aprobación", "type": "document", "required": True, "extensions": [".pdf"]},
                ],
                "rules": [
                    {"type": "max_ref", "field": "approved_amount", "ref": "1.budget",
                     "message": "El valor aprobado supera el presupuesto disponible."},
                    {"type": "equals_ref", "field": "approved_amount", "ref": "2.quoted_amount",
                     "message": "El valor aprobado no coincide con el valor cotizado seleccionado."},
                ],
            },
            {
                "name": "Ejecución y cierre",
                "description": "Recepción, facturación y cierre.",
                "planned_days": 15,
                "requirements": [
                    {"key": "delivery_date", "label": "Fecha de entrega", "type": "date", "required": True},
                    {"key": "invoiced_amount", "label": "Valor facturado (COP)", "type": "number", "required": True, "min": 1},
                    {"key": "invoice_doc", "label": "Factura", "type": "document", "required": True, "extensions": [".pdf", ".xml"]},
                    {"key": "received_ok", "label": "Recibido a satisfacción", "type": "checklist", "required": True},
                ],
                "rules": [
                    {"type": "max_ref", "field": "invoiced_amount", "ref": "3.approved_amount",
                     "message": "El valor facturado supera el valor aprobado."},
                    {"type": "date_after_ref", "field": "delivery_date", "ref": "3.approval_date",
                     "message": "La entrega ocurrió antes de la aprobación del gasto."},
                ],
            },
        ],
    },
    "business_project": {
        "key": "business_project",
        "name": "Proyecto empresarial",
        "category": "business",
        "description": "Gestión de un proyecto empresarial: inicio, planificación, ejecución y cierre.",
        "phases": [
            {
                "name": "Inicio",
                "description": "Acta de constitución y patrocinio.",
                "planned_days": 7,
                "requirements": [
                    {"key": "objective", "label": "Objetivo del proyecto", "type": "text", "required": True, "min_length": 60},
                    {"key": "sponsor", "label": "Patrocinador", "type": "text", "required": True, "min_length": 5},
                    {"key": "budget", "label": "Presupuesto (COP)", "type": "number", "required": True, "min": 1},
                    {"key": "start_date", "label": "Fecha de inicio", "type": "date", "required": True},
                    {"key": "end_date", "label": "Fecha de cierre planeada", "type": "date", "required": True},
                    {"key": "charter_doc", "label": "Acta de constitución", "type": "document", "required": True, "extensions": [".pdf", ".docx"]},
                ],
                "rules": [
                    {"type": "date_order", "first": "start_date", "second": "end_date",
                     "message": "La fecha de inicio es posterior a la de cierre."},
                ],
            },
            {
                "name": "Planificación",
                "description": "Cronograma, hitos y riesgos.",
                "planned_days": 14,
                "requirements": [
                    {"key": "milestones", "label": "Número de hitos", "type": "number", "required": True, "min": 1},
                    {"key": "risks", "label": "Riesgos identificados", "type": "text", "required": True, "min_length": 60},
                    {"key": "schedule_doc", "label": "Cronograma", "type": "document", "required": True, "extensions": [".pdf", ".xlsx", ".mpp"]},
                    {"key": "plan_approved", "label": "Plan aprobado por el patrocinador", "type": "checklist", "required": True},
                ],
                "rules": [],
            },
            {
                "name": "Ejecución",
                "description": "Desarrollo de entregables y control de costos.",
                "planned_days": 60,
                "requirements": [
                    {"key": "progress", "label": "Avance (%)", "type": "number", "required": True, "min": 0, "max": 100},
                    {"key": "spent", "label": "Gasto ejecutado (COP)", "type": "number", "required": True, "min": 0},
                    {"key": "status_report", "label": "Informe de estado", "type": "text", "required": True, "min_length": 60},
                    {"key": "deliverables_doc", "label": "Evidencia de entregables", "type": "document", "required": True, "extensions": [".pdf", ".zip", ".docx"]},
                ],
                "rules": [
                    {"type": "max_ref", "field": "spent", "ref": "1.budget",
                     "message": "El gasto ejecutado supera el presupuesto del proyecto."},
                    {"type": "min_value", "field": "progress", "value": 100,
                     "message": "El avance es menor al 100%; la ejecución no puede cerrarse."},
                ],
            },
            {
                "name": "Cierre",
                "description": "Entrega formal y lecciones aprendidas.",
                "planned_days": 7,
                "requirements": [
                    {"key": "lessons", "label": "Lecciones aprendidas", "type": "text", "required": True, "min_length": 60},
                    {"key": "closing_date", "label": "Fecha de cierre real", "type": "date", "required": True},
                    {"key": "closing_doc", "label": "Acta de cierre", "type": "document", "required": True, "extensions": [".pdf"]},
                    {"key": "client_ok", "label": "Aceptación del cliente", "type": "checklist", "required": True},
                ],
                "rules": [
                    {"type": "date_after_ref", "field": "closing_date", "ref": "1.start_date",
                     "message": "La fecha de cierre es anterior al inicio del proyecto."},
                ],
            },
        ],
    },
}


def list_templates() -> list[dict]:
    return [
        {
            "key": t["key"],
            "name": t["name"],
            "category": t["category"],
            "description": t["description"],
            "phases": [{"name": p["name"], "planned_days": p["planned_days"],
                        "requirements": len(p["requirements"])} for p in t["phases"]],
        }
        for t in TEMPLATES.values()
    ]


def get_template(key: str) -> dict | None:
    return TEMPLATES.get(key)
