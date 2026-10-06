"""Recommendation generator: turns findings and risk into actionable advice."""
from __future__ import annotations

from app.ai.rules_engine import Finding
from app.ai.risk_model import RiskPrediction

CATEGORY_ADVICE = {
    "requirement": "Complete los campos obligatorios señalados antes de solicitar el avance de fase.",
    "document": "Adjunte los documentos soporte en el formato solicitado; sin evidencia la fase no puede aprobarse.",
    "consistency": "Revise los datos inconsistentes contra las fases anteriores; corrija el valor o justifique el cambio.",
    "quality": "Reemplace el texto provisional por información definitiva y específica.",
}

FACTOR_ADVICE = {
    "time_ratio": "La fase consume más tiempo del planeado: priorice los requisitos pendientes o solicite ajuste del cronograma.",
    "completion_ratio": "El nivel de cumplimiento es bajo para el tiempo transcurrido: asigne responsables a cada requisito faltante.",
    "rejections": "La fase ha sido rechazada varias veces: programe una revisión con el responsable antes de volver a validar.",
    "prev_delay_days": "El proceso arrastra retrasos de fases previas: considere reprogramar las fechas de las fases siguientes.",
    "error_count": "Hay varios errores bloqueantes: resuélvalos primero, son los que más elevan el riesgo.",
    "phase_position": "Es una fase avanzada: un retraso aquí impacta directamente la fecha de cierre del proceso.",
}


def build_recommendations(findings: list[Finding], risk: RiskPrediction) -> list[dict]:
    recommendations: list[dict] = []
    seen_categories = set()

    # 1) One recommendation per category of problem, prioritized by severity
    for finding in sorted(findings, key=lambda f: {"error": 0, "warning": 1, "info": 2}[f.severity]):
        if finding.category in CATEGORY_ADVICE and finding.category not in seen_categories:
            seen_categories.add(finding.category)
            recommendations.append({
                "priority": "alta" if finding.severity == "error" else "media",
                "text": CATEGORY_ADVICE[finding.category],
            })

    # 2) Deadline-specific advice
    if any(f.code == "deadline:overdue" for f in findings):
        recommendations.append({"priority": "alta",
                                "text": "La fase está vencida: notifique al responsable y registre una nueva fecha comprometida."})
    elif any(f.code == "deadline:near" for f in findings):
        recommendations.append({"priority": "media",
                                "text": "La fecha límite está próxima: valide hoy los requisitos para evitar bloqueos."})

    # 3) Advice derived from the ML risk factors
    if risk.level in ("medium", "high"):
        for factor in risk.factors:
            advice = FACTOR_ADVICE.get(factor["feature"])
            if advice:
                recommendations.append({"priority": "alta" if risk.level == "high" else "media", "text": advice})

    if not recommendations:
        recommendations.append({"priority": "baja",
                                "text": "La fase cumple los requisitos y el riesgo de retraso es bajo. Puede continuar."})
    return recommendations


def build_summary(passed: bool, score: float, risk: RiskPrediction, findings: list[Finding]) -> str:
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    risk_text = {"low": "bajo", "medium": "medio", "high": "alto"}[risk.level]
    if passed:
        head = f"Fase validada con un cumplimiento de {score:.0f}/100."
    else:
        head = f"Fase NO validada: cumplimiento de {score:.0f}/100 con {errors} error(es) bloqueante(s)."
    tail = f" Riesgo de retraso {risk_text} ({risk.probability * 100:.0f}%)."
    if warnings:
        tail += f" {warnings} advertencia(s) por revisar."
    return head + tail
