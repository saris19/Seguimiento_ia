"""
AI supervisor: orchestrates the hybrid validation of a phase.

    rules engine (deterministic)  ──┐
                                    ├──► score + decision + alerts + recommendations
    delay-risk model (ML)        ───┘
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.ai.recommender import build_recommendations, build_summary
from app.ai.risk_model import get_model, RiskPrediction
from app.ai.rules_engine import evaluate_phase, Finding
from app.config import MIN_SCORE_TO_ADVANCE

SEVERITY_PENALTY = {"error": 0, "warning": 5, "info": 0}   # requirement errors already reduce completion
CONSISTENCY_ERROR_PENALTY = 15
DEADLINE_ERROR_PENALTY = 10


@dataclass
class SupervisorResult:
    passed: bool
    score: float
    findings: list[Finding]
    risk: RiskPrediction
    recommendations: list[dict]
    summary: str
    features: dict


def compute_score(completion_ratio: float, findings: list[Finding]) -> float:
    score = 100 * completion_ratio
    for f in findings:
        score -= SEVERITY_PENALTY[f.severity]
        if f.severity == "error" and f.category == "consistency":
            score -= CONSISTENCY_ERROR_PENALTY
        if f.category == "deadline" and f.alert_level == "critical":
            score -= DEADLINE_ERROR_PENALTY
    return round(max(0.0, min(100.0, score)), 1)


def supervise_phase(*, requirements: list[dict], rules: list[dict], submission: dict,
                    previous_fields: dict[int, dict], phase_order: int, total_phases: int,
                    start: date | None, due: date | None, planned_days: int,
                    rejections: int, prev_delay_days: int, today: date | None = None) -> SupervisorResult:
    today = today or date.today()

    rules_result = evaluate_phase(requirements, rules, submission, previous_fields,
                                  phase_order, start, due, today)
    findings = rules_result.findings
    score = compute_score(rules_result.completion_ratio, findings)

    elapsed = (today - start).days if start else 0
    features = {
        "completion_ratio": rules_result.completion_ratio,
        "time_ratio": max(elapsed, 0) / max(planned_days, 1),
        "rejections": rejections,
        "prev_delay_days": prev_delay_days,
        "phase_position": phase_order / max(total_phases, 1),
        "error_count": sum(1 for f in findings if f.severity == "error"),
    }
    risk = get_model().predict(features)

    passed = not rules_result.has_errors and score >= MIN_SCORE_TO_ADVANCE
    recommendations = build_recommendations(findings, risk)
    summary = build_summary(passed, score, risk, findings)

    return SupervisorResult(passed, score, findings, risk, recommendations, summary, features)
