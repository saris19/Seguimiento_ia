"""Automatic compliance report per process (JSON + printable HTML)."""
from __future__ import annotations

from datetime import date, datetime
from html import escape

from app.models import Process
from app.services.serializers import process_progress

STATUS_LABELS = {"pending": "Pendiente", "in_progress": "En curso", "blocked": "Bloqueada", "approved": "Cumplida"}
PROCESS_STATUS_LABELS = {"active": "Activo", "blocked": "Bloqueado", "completed": "Finalizado"}
CATEGORY_LABELS = {"academic": "Académico", "administrative": "Administrativo", "business": "Empresarial"}


def build_report(process: Process, today: date | None = None) -> dict:
    today = today or date.today()
    phases = []
    total_delay = 0
    scores = []

    for p in process.phases:
        end = p.completed_at or (today if p.start_date else None)
        actual_days = (end - p.start_date).days if p.start_date and end else None
        delay = 0
        if p.due_date:
            ref = p.completed_at or today
            if p.status != "pending":
                delay = max(0, (ref - p.due_date).days)
        total_delay += delay
        last = p.validations[0] if p.validations else None
        if p.last_score is not None:
            scores.append(p.last_score)
        phases.append({
            "order": p.order,
            "name": p.name,
            "status": p.status,
            "status_label": STATUS_LABELS[p.status],
            "planned_days": p.planned_days,
            "actual_days": actual_days,
            "delay_days": delay,
            "score": p.last_score,
            "risk": p.last_risk,
            "validations": len(p.validations),
            "rejections": p.rejections,
            "issues": [f for f in (last.findings if last else []) if f["severity"] in ("error", "warning")],
            "summary": last.summary if last else "Sin validaciones registradas.",
        })

    open_alerts = [a for a in process.alerts if not a.resolved]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "process": {
            "id": process.id, "name": process.name, "owner": process.owner,
            "category": CATEGORY_LABELS.get(process.category, process.category),
            "status": PROCESS_STATUS_LABELS.get(process.status, process.status),
            "start_date": process.start_date.isoformat(),
        },
        "overview": {
            "progress": process_progress(process),
            "average_score": avg_score,
            "total_delay_days": total_delay,
            "total_validations": sum(ph["validations"] for ph in phases),
            "total_rejections": sum(ph["rejections"] for ph in phases),
            "open_alerts": len(open_alerts),
            "critical_alerts": sum(1 for a in open_alerts if a.level == "critical"),
        },
        "phases": phases,
    }
    report["conclusions"] = _conclusions(report)
    return report


def _conclusions(report: dict) -> list[str]:
    ov, phases = report["overview"], report["phases"]
    lines = [f"El proceso presenta un avance del {ov['progress']:.0f}% "
             f"({sum(1 for p in phases if p['status'] == 'approved')} de {len(phases)} fases cumplidas)."]
    if ov["average_score"] is not None:
        quality = "alto" if ov["average_score"] >= 85 else "aceptable" if ov["average_score"] >= 70 else "bajo"
        lines.append(f"El cumplimiento promedio validado por la IA es {quality} ({ov['average_score']:.0f}/100).")
    if ov["total_delay_days"] > 0:
        late = [p["name"] for p in phases if p["delay_days"] > 0]
        lines.append(f"Se acumulan {ov['total_delay_days']} día(s) de retraso, concentrados en: {', '.join(late)}.")
    else:
        lines.append("No se registran retrasos frente a lo planeado.")
    worst = max(phases, key=lambda p: p["rejections"])
    if worst["rejections"] > 0:
        lines.append(f"La fase con más rechazos es «{worst['name']}» ({worst['rejections']}); "
                     "conviene revisar la claridad de sus requisitos.")
    if ov["critical_alerts"]:
        lines.append(f"Hay {ov['critical_alerts']} alerta(s) crítica(s) abiertas que requieren atención inmediata.")
    return lines


def render_report_html(report: dict) -> str:
    p, ov = report["process"], report["overview"]
    rows = []
    for ph in report["phases"]:
        issues = "".join(f"<li>{escape(i['message'])}</li>" for i in ph["issues"]) or "<li>Sin observaciones</li>"
        rows.append(f"""
        <tr>
          <td>{ph['order']}. {escape(ph['name'])}</td>
          <td><span class="tag {ph['status']}">{ph['status_label']}</span></td>
          <td class="num">{ph['planned_days']}</td>
          <td class="num">{ph['actual_days'] if ph['actual_days'] is not None else '—'}</td>
          <td class="num">{ph['delay_days']}</td>
          <td class="num">{f"{ph['score']:.0f}" if ph['score'] is not None else '—'}</td>
          <td class="num">{f"{ph['risk']*100:.0f}%" if ph['risk'] is not None else '—'}</td>
          <td class="num">{ph['validations']} / {ph['rejections']}</td>
          <td><ul>{issues}</ul></td>
        </tr>""")
    conclusions = "".join(f"<li>{escape(c)}</li>" for c in report["conclusions"])
    avg = f"{ov['average_score']:.0f}" if ov["average_score"] is not None else "—"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reporte de cumplimiento — {escape(p['name'])}</title>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#16181d;margin:40px auto;max-width:1100px;padding:0 24px}}
  h1{{font-size:28px;margin:0 0 4px}} .meta{{color:#5b6170;font-size:14px;margin-bottom:24px}}
  .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:28px}}
  .kpi{{border:1px solid #e3e5ea;border-radius:8px;padding:14px}} .kpi b{{display:block;font-size:24px}}
  .kpi span{{font-size:12px;color:#5b6170;text-transform:uppercase;letter-spacing:.04em}}
  table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border-bottom:1px solid #e3e5ea;padding:8px;text-align:left;vertical-align:top}}
  th{{font-size:11px;text-transform:uppercase;color:#5b6170}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
  ul{{margin:0;padding-left:16px}} .tag{{padding:2px 8px;border-radius:4px;font-size:12px;background:#eef0f3}}
  .approved{{background:#e3f5ea;color:#17663a}} .blocked{{background:#fde8e8;color:#9b1c1c}} .in_progress{{background:#fff4d6;color:#7a5200}}
  h2{{font-size:18px;margin-top:32px}} footer{{margin-top:40px;font-size:12px;color:#5b6170}}
  @media print{{body{{margin:0}} button{{display:none}}}}
</style></head><body>
<button onclick="window.print()" style="float:right;padding:8px 14px">Imprimir / PDF</button>
<h1>Reporte de cumplimiento</h1>
<div class="meta">{escape(p['name'])} · {escape(p['category'])} · Responsable: {escape(p['owner'])} ·
Estado: {escape(p['status'])} · Generado: {report['generated_at'].replace('T', ' ')}</div>
<div class="kpis">
  <div class="kpi"><span>Avance</span><b>{ov['progress']:.0f}%</b></div>
  <div class="kpi"><span>Cumplimiento IA</span><b>{avg}</b></div>
  <div class="kpi"><span>Días de retraso</span><b>{ov['total_delay_days']}</b></div>
  <div class="kpi"><span>Validaciones / rechazos</span><b>{ov['total_validations']} / {ov['total_rejections']}</b></div>
  <div class="kpi"><span>Alertas abiertas</span><b>{ov['open_alerts']}</b></div>
</div>
<h2>Conclusiones de la IA</h2><ul>{conclusions}</ul>
<h2>Detalle por fase</h2>
<table><thead><tr><th>Fase</th><th>Estado</th><th class="num">Días plan</th><th class="num">Días reales</th>
<th class="num">Retraso</th><th class="num">Puntaje</th><th class="num">Riesgo</th><th class="num">Valid./Rech.</th><th>Observaciones</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<footer>Reporte generado automáticamente por el supervisor de IA (motor de reglas + modelo de riesgo de retraso).</footer>
</body></html>"""
