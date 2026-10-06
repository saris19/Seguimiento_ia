"""
Machine-learning component of the AI supervisor: delay-risk prediction.

A logistic regression model estimates the probability that the current phase
finishes late. It is trained on a historical dataset of phase executions. In
this prototype the history is *synthetic* (generated with a reproducible
seed and realistic relationships); in production it will be replaced by the
platform's own historical records (see README, "pendiente").

Logistic regression is used on purpose: it is explainable, so the supervisor
can tell the user *which factors* push the risk up.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import DATA_DIR, HIGH_RISK_THRESHOLD, MEDIUM_RISK_THRESHOLD

FEATURES = [
    "completion_ratio",   # share of requirements satisfied (0–1)
    "time_ratio",         # elapsed days / planned days
    "rejections",         # failed validations in this phase
    "prev_delay_days",    # accumulated delay of previous phases
    "phase_position",     # phase order / total phases (0–1)
    "error_count",        # blocking findings in the current validation
]

FEATURE_LABELS = {
    "completion_ratio": "Bajo nivel de cumplimiento de requisitos",
    "time_ratio": "Alto consumo del tiempo planeado",
    "rejections": "Validaciones rechazadas previamente",
    "prev_delay_days": "Retrasos acumulados en fases anteriores",
    "phase_position": "Fase avanzada del proceso",
    "error_count": "Errores bloqueantes pendientes",
}

# Features where a LOW value increases the risk
INVERSE_FEATURES = {"completion_ratio"}


@dataclass
class RiskPrediction:
    probability: float
    level: str               # low | medium | high
    factors: list[dict]      # main factors pushing risk up


def generate_history(n_samples: int = 3000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Generate a reproducible synthetic history of phase executions."""
    rng = np.random.default_rng(seed)
    completion = rng.beta(4, 2, n_samples)
    time_ratio = rng.gamma(2.5, 0.35, n_samples)
    rejections = rng.poisson(0.8, n_samples)
    prev_delay = np.clip(rng.exponential(4, n_samples) * (rng.random(n_samples) < 0.45), 0, 60)
    position = rng.choice([0.25, 0.5, 0.75, 1.0], n_samples)
    errors = np.clip(np.round((1 - completion) * 6 + rng.normal(0, 0.8, n_samples)), 0, None)

    logit = (-2.0 + 2.6 * time_ratio - 2.4 * completion + 0.55 * rejections
             + 0.07 * prev_delay + 0.30 * errors + 0.4 * position + rng.normal(0, 0.6, n_samples))
    prob = 1 / (1 + np.exp(-logit))
    delayed = (rng.random(n_samples) < prob).astype(int)

    X = np.column_stack([completion, time_ratio, rejections, prev_delay, position, errors])
    return X, delayed


class DelayRiskModel:
    def __init__(self):
        self.pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000)),
        ])
        self.metrics: dict = {}
        self._train()

    def _train(self):
        X, y = generate_history()
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=7, stratify=y)
        self.pipeline.fit(X_train, y_train)
        proba = self.pipeline.predict_proba(X_test)[:, 1]
        self.metrics = {
            "algorithm": "Regresión logística (scikit-learn) con estandarización",
            "training_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "accuracy": round(float(accuracy_score(y_test, proba >= 0.5)), 3),
            "roc_auc": round(float(roc_auc_score(y_test, proba)), 3),
            "delay_rate": round(float(y.mean()), 3),
            "features": FEATURES,
            "coefficients": {
                f: round(float(c), 3) for f, c in zip(FEATURES, self.pipeline.named_steps["clf"].coef_[0])
            },
            "data_source": "Histórico sintético reproducible (semilla 42)",
        }
        self._export_history(X, y)

    @staticmethod
    def _export_history(X: np.ndarray, y: np.ndarray):
        path = DATA_DIR / "training_history.csv"
        if path.exists():
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(FEATURES + ["delayed"])
            for row, label in zip(X, y):
                writer.writerow([round(float(v), 4) for v in row] + [int(label)])

    def predict(self, features: dict) -> RiskPrediction:
        x = np.array([[float(features[f]) for f in FEATURES]])
        probability = float(self.pipeline.predict_proba(x)[0, 1])

        # Explain: contribution of each standardized feature to the logit
        scaler = self.pipeline.named_steps["scaler"]
        coefs = self.pipeline.named_steps["clf"].coef_[0]
        contributions = coefs * (x[0] - scaler.mean_) / scaler.scale_
        factors = [
            {"feature": f, "label": FEATURE_LABELS[f], "value": round(float(features[f]), 3),
             "impact": round(float(c), 3)}
            for f, c in zip(FEATURES, contributions) if c > 0.15
        ]
        factors.sort(key=lambda item: item["impact"], reverse=True)

        if probability >= HIGH_RISK_THRESHOLD:
            level = "high"
        elif probability >= MEDIUM_RISK_THRESHOLD:
            level = "medium"
        else:
            level = "low"
        return RiskPrediction(round(probability, 3), level, factors[:3])


_model: DelayRiskModel | None = None


def get_model() -> DelayRiskModel:
    global _model
    if _model is None:
        _model = DelayRiskModel()
    return _model
