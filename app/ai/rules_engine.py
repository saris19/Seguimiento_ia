"""
Rules engine: deterministic part of the AI supervisor.

It verifies that each requirement of a phase is met, checks consistency rules
(within the phase and against previous phases), deadlines and the quality of
the submitted text. Every problem is returned as a *finding*.

Finding severities:
  - error:   blocks the phase from advancing
  - warning: does not block, but lowers the score and generates an alert
  - info:    informative observation
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field as dc_field
from datetime import date
from pathlib import Path

from app.config import PLACEHOLDER_WORDS, DEADLINE_WARNING_RATIO


@dataclass
class Finding:
    code: str
    severity: str           # error | warning | info
    category: str           # requirement | document | consistency | deadline | quality
    message: str
    field: str | None = None
    alert_level: str | None = None   # overrides the default alert level when set

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RulesResult:
    findings: list[Finding] = dc_field(default_factory=list)
    total_requirements: int = 0
    satisfied_requirements: int = 0

    @property
    def completion_ratio(self) -> float:
        if self.total_requirements == 0:
            return 1.0
        return self.satisfied_requirements / self.total_requirements

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self.findings)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def resolve_reference(ref: str, current_fields: dict, all_fields: dict[int, dict]):
    """Resolve "2.approved_amount" (phase 2) or "budget" (current phase)."""
    if "." in ref:
        order_str, key = ref.split(".", 1)
        return all_fields.get(int(order_str), {}).get(key)
    return current_fields.get(ref)


# --------------------------------------------------------------------------- #
# Requirement checks
# --------------------------------------------------------------------------- #
def _check_requirement(req: dict, fields: dict, documents: dict) -> Finding | None:
    key, label, req_type = req["key"], req["label"], req["type"]
    required = req.get("required", True)

    if req_type == "document":
        doc = documents.get(key)
        if not doc:
            return Finding(f"missing_doc:{key}", "error" if required else "warning", "document",
                           f"Falta el documento obligatorio «{label}».", key) if required else None
        ext = Path(doc.get("filename", "")).suffix.lower()
        allowed = req.get("extensions")
        if allowed and ext not in allowed:
            return Finding(f"bad_ext:{key}", "error", "document",
                           f"«{label}» tiene formato {ext or 'desconocido'}; se esperaba {', '.join(allowed)}.", key)
        if doc.get("size", 0) <= 0:
            return Finding(f"empty_doc:{key}", "error", "document", f"El archivo de «{label}» está vacío.", key)
        return None

    value = fields.get(key)

    if req_type == "checklist":
        if required and value is not True:
            return Finding(f"unchecked:{key}", "error", "requirement",
                           f"No se ha confirmado: «{label}».", key)
        return None

    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            return Finding(f"missing:{key}", "error", "requirement", f"El campo «{label}» es obligatorio.", key)
        return None

    if req_type == "text":
        text = str(value).strip()
        min_len = req.get("min_length", 0)
        if len(text) < min_len:
            return Finding(f"short:{key}", "error", "requirement",
                           f"«{label}» es demasiado corto ({len(text)} de {min_len} caracteres mínimos).", key)

    elif req_type == "number":
        number = _parse_number(value)
        if number is None:
            return Finding(f"nan:{key}", "error", "requirement", f"«{label}» debe ser un número.", key)
        if "min" in req and number < req["min"]:
            return Finding(f"range:{key}", "error", "requirement", f"«{label}» debe ser ≥ {req['min']}.", key)
        if "max" in req and number > req["max"]:
            return Finding(f"range:{key}", "error", "requirement", f"«{label}» debe ser ≤ {req['max']}.", key)

    elif req_type == "date":
        if _parse_date(value) is None:
            return Finding(f"bad_date:{key}", "error", "requirement", f"«{label}» no es una fecha válida.", key)

    elif req_type == "select":
        options = req.get("options", [])
        if options and value not in options:
            return Finding(f"bad_option:{key}", "error", "requirement",
                           f"«{label}» tiene un valor no permitido.", key)
    return None


def _check_text_quality(req: dict, fields: dict) -> Finding | None:
    """Detect placeholder or low-effort content in text fields."""
    if req["type"] != "text":
        return None
    text = str(fields.get(req["key"]) or "").lower()
    if not text:
        return None
    tokens = re.findall(r"[a-záéíóúñü/]+", text)
    for word in PLACEHOLDER_WORDS:
        if word in tokens or (" " in word and word in text):
            return Finding(f"placeholder:{req['key']}", "warning", "quality",
                           f"«{req['label']}» parece contener texto provisional («{word}»).", req["key"])
    words = tokens
    if len(words) >= 8 and len(set(words)) / len(words) < 0.4:
        return Finding(f"repetitive:{req['key']}", "warning", "quality",
                       f"«{req['label']}» tiene contenido muy repetitivo.", req["key"])
    return None


# --------------------------------------------------------------------------- #
# Consistency rules
# --------------------------------------------------------------------------- #
def _check_rule(rule: dict, fields: dict, all_fields: dict[int, dict]) -> Finding | None:
    rule_type = rule["type"]
    message = rule.get("message", "Inconsistencia detectada.")
    target = rule.get("field") or rule.get("second")
    code = f"rule:{rule_type}:{target}"

    if rule_type == "date_order":
        first, second = _parse_date(fields.get(rule["first"])), _parse_date(fields.get(rule["second"]))
        if first and second and first > second:
            return Finding(code, "error", "consistency", message, rule["second"])

    elif rule_type == "date_after_ref":
        value = _parse_date(fields.get(rule["field"]))
        ref = _parse_date(resolve_reference(rule["ref"], fields, all_fields))
        if value and ref and value < ref:
            return Finding(code, "error", "consistency", message, rule["field"])

    elif rule_type in ("max_ref", "equals_ref"):
        value = _parse_number(fields.get(rule["field"]))
        ref = _parse_number(resolve_reference(rule["ref"], fields, all_fields))
        if value is None or ref is None:
            return None
        if rule_type == "max_ref" and value > ref:
            return Finding(code, "error", "consistency", f"{message} ({value:,.0f} > {ref:,.0f})", rule["field"])
        if rule_type == "equals_ref" and abs(value - ref) > 0.005 * max(abs(ref), 1):
            return Finding(code, "warning", "consistency", f"{message} ({value:,.0f} ≠ {ref:,.0f})", rule["field"])

    elif rule_type == "min_value":
        value = _parse_number(fields.get(rule["field"]))
        if value is not None and value < rule["value"]:
            return Finding(code, "error", "consistency", message, rule["field"])

    elif rule_type == "forbidden_value":
        if fields.get(rule["field"]) == rule["value"]:
            return Finding(code, "error", "consistency", message, rule["field"])

    return None


# --------------------------------------------------------------------------- #
# Deadline check
# --------------------------------------------------------------------------- #
def check_deadline(start: date | None, due: date | None, today: date) -> Finding | None:
    if not start or not due:
        return None
    if today > due:
        # A delay never blocks by itself (otherwise an overdue phase could never be closed);
        # it lowers the score and raises a critical alert when it exceeds one week.
        days_late = (today - due).days
        return Finding("deadline:overdue", "warning", "deadline",
                       f"La fase está vencida hace {days_late} día(s) (fecha límite {due.isoformat()}).",
                       alert_level="critical" if days_late > 7 else "warning")
    total = max((due - start).days, 1)
    elapsed = (today - start).days
    if elapsed / total >= DEADLINE_WARNING_RATIO:
        remaining = (due - today).days
        return Finding("deadline:near", "info", "deadline",
                       f"Quedan {remaining} día(s) para la fecha límite de la fase.")
    return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def evaluate_phase(requirements: list[dict], rules: list[dict], submission: dict,
                   previous_fields: dict[int, dict], phase_order: int,
                   start: date | None, due: date | None, today: date | None = None) -> RulesResult:
    today = today or date.today()
    fields = submission.get("fields", {}) or {}
    documents = submission.get("documents", {}) or {}
    all_fields = {**previous_fields, phase_order: fields}

    result = RulesResult(total_requirements=len(requirements))

    for req in requirements:
        finding = _check_requirement(req, fields, documents)
        if finding:
            result.findings.append(finding)
        else:
            result.satisfied_requirements += 1
            quality = _check_text_quality(req, fields)
            if quality:
                result.findings.append(quality)

    for rule in rules:
        finding = _check_rule(rule, fields, all_fields)
        if finding:
            result.findings.append(finding)

    deadline = check_deadline(start, due, today)
    if deadline:
        result.findings.append(deadline)

    return result
