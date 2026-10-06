/* ==========================================================================
   ProcesIA — front-end (vanilla JS, hash routing)
   ========================================================================== */
const mainEl = document.getElementById("main");

const LABELS = {
  processStatus: { active: "Activo", blocked: "Bloqueado", completed: "Finalizado" },
  phaseStatus: { pending: "Pendiente", in_progress: "En curso", blocked: "Bloqueada", approved: "Cumplida" },
  category: { academic: "Académico", administrative: "Administrativo", business: "Empresarial" },
  level: { critical: "Crítica", warning: "Advertencia", info: "Info" },
  kind: { error: "Error", delay: "Retraso", inconsistency: "Inconsistencia", risk: "Riesgo", status: "Estado" },
  severity: { error: "Error", warning: "Advertencia", info: "Info" },
  risk: { low: "Bajo", medium: "Medio", high: "Alto" },
};

const TONE = {
  active: "info", blocked: "err", completed: "ok",
  pending: "plain", in_progress: "info", approved: "ok",
  critical: "err", warning: "warn", info: "info", error: "err",
  low: "ok", medium: "warn", high: "err",
};

/* ---------------------------------------------------------------- helpers */
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const fmtDate = (iso) => iso ? new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("es-CO",
  { day: "2-digit", month: "short", year: "numeric" }) : "—";
const fmtPct = (v) => v == null ? "—" : `${Math.round(v * 100)}%`;
const riskLevel = (p) => p == null ? null : p >= 0.65 ? "high" : p >= 0.4 ? "medium" : "low";

async function api(path, options = {}) {
  const opts = { ...options };
  if (opts.json !== undefined) {
    opts.body = JSON.stringify(opts.json);
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    delete opts.json;
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try { const body = await res.json(); detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail); } catch (_) { /* no body */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

function toast(message, tone = "") {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = `toast ${tone ? "toast--" + tone : ""}`;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 4200);
}

async function withLoading(button, fn) {
  button.classList.add("is-loading");
  const original = button.innerHTML;
  button.innerHTML = button.dataset.loading || "Procesando…";
  try { return await fn(); } finally { button.classList.remove("is-loading"); button.innerHTML = original; }
}

/* -------------------------------------------------------------- components */
const tag = (text, tone = "plain") => `<span class="tag tag--${tone}">${esc(text)}</span>`;
const statusTag = (s, dict = LABELS.processStatus) => tag(dict[s] || s, TONE[s] || "plain");

const pageHead = (eyebrow, title, lead, actions = "") => `
  <div class="page-head fade-in">
    <div><div class="eyebrow">${esc(eyebrow)}</div><h1 class="display">${title}</h1>
    ${lead ? `<p class="lead">${lead}</p>` : ""}</div>
    ${actions ? `<div>${actions}</div>` : ""}
  </div>`;

const kpi = (label, value, note = "", mod = "") => `
  <div class="kpi ${mod}"><div class="kpi__label">${esc(label)}</div>
  <div class="kpi__value">${esc(value)}</div><div class="kpi__note">${esc(note)}</div></div>`;

const bar = (ratio, risk = false) =>
  `<div class="bar ${risk ? "bar--risk" : ""}" role="img" aria-label="${Math.round(ratio * 100)}%"><span style="width:${Math.min(100, Math.max(0, ratio * 100))}%"></span></div>`;

const emptyState = (title, text, action = "") =>
  `<div class="empty"><h3>${esc(title)}</h3><p>${esc(text)}</p>${action ? `<div style="margin-top:16px">${action}</div>` : ""}</div>`;

function processTable(processes) {
  if (!processes.length) return emptyState("Aún no hay procesos", "Cree el primero a partir de una plantilla.",
    `<a class="btn btn--primary" href="#/new">Nuevo proceso →</a>`);
  return `<div class="table-wrap"><table>
    <thead><tr><th>Proceso</th><th class="hide-sm">Tipo</th><th>Estado</th><th>Fase actual</th>
    <th>Avance</th><th class="num">Riesgo IA</th><th class="num">Alertas</th></tr></thead>
    <tbody>${processes.map((p) => `
      <tr>
        <td><a class="row-link" href="#/process/${p.id}">${esc(p.name)}</a>
          <div class="small muted">${esc(p.owner)}</div></td>
        <td class="hide-sm muted">${esc(LABELS.category[p.category])}</td>
        <td>${statusTag(p.status)}</td>
        <td>${p.current_phase ? `${esc(p.current_phase)} <span class="small muted mono">${p.current_phase_order}/${p.total_phases}</span>` : "—"}
          ${p.is_overdue && p.status !== "completed" ? ` ${tag("Vencida", "err")}` : ""}</td>
        <td><div class="progress-cell">${bar(p.progress / 100)}<span class="mono small">${Math.round(p.progress)}%</span></div></td>
        <td class="num">${p.current_risk == null ? "—" : tag(fmtPct(p.current_risk), TONE[riskLevel(p.current_risk)])}</td>
        <td class="num mono">${p.open_alerts ? `<span style="color:var(--${p.critical_alerts ? "err" : "warn"})">${p.open_alerts}</span>` : "0"}</td>
      </tr>`).join("")}</tbody></table></div>`;
}

function alertList(alerts, { showProcess = true, resolvable = false } = {}) {
  if (!alerts.length) return emptyState("Sin alertas abiertas", "La IA no ha detectado errores, retrasos ni inconsistencias pendientes.");
  return `<ul class="alert-list">${alerts.map((a) => `
    <li class="alert-item">
      <span class="dot dot--${a.level}" aria-hidden="true"></span>
      <div><div class="alert-item__msg">${esc(a.message)}</div>
        <div class="alert-item__meta">${esc(LABELS.level[a.level])} · ${esc(LABELS.kind[a.kind] || a.kind)}
        ${showProcess ? ` · <a href="#/process/${a.process_id}">${esc(a.process_name)}</a>` : ""} · ${esc(a.created_at.replace("T", " ").slice(0, 16))}</div></div>
      ${resolvable && !a.resolved ? `<button class="btn btn--sm" data-resolve="${a.id}">Resolver</button>` : "<span></span>"}
    </li>`).join("")}</ul>`;
}

function aiPanel(v) {
  if (!v) return `<section class="panel" aria-label="Supervisor IA">
    <div class="panel__head"><span class="panel__title">Supervisor IA</span></div>
    ${emptyState("Fase sin validar", "Diligencie los requisitos y pulse «Validar con IA» para obtener el diagnóstico.")}</section>`;

  const findings = v.findings.length
    ? v.findings.map((f) => `<div class="finding">${tag(LABELS.severity[f.severity], TONE[f.severity])}<span>${esc(f.message)}</span></div>`).join("")
    : `<p class="small muted">Sin hallazgos: todos los requisitos se cumplen.</p>`;
  const factors = v.risk_factors.length
    ? v.risk_factors.map((f) => `<div class="factor"><span>${esc(f.label)}</span>${bar(Math.min(f.impact / 3, 1), true)}</div>`).join("")
    : `<p class="small muted">Ningún factor eleva significativamente el riesgo.</p>`;

  return `<section class="panel fade-in" aria-label="Supervisor IA">
    <div class="panel__head"><span class="panel__title">Supervisor IA</span>
      ${v.passed ? tag("Validada", "ok") : tag("No validada", "err")}</div>
    <div class="ai-score">
      <div><div class="kpi__label">Cumplimiento</div><div class="ai-score__value" style="color:var(--${v.score >= 70 ? "ok" : "err"})">${Math.round(v.score)}</div>${bar(v.score / 100)}</div>
      <div><div class="kpi__label">Riesgo de retraso</div><div class="ai-score__value" style="color:var(--${TONE[v.risk_level]})">${fmtPct(v.risk_probability)}</div>${bar(v.risk_probability, true)}</div>
    </div>
    <p class="ai-summary">${esc(v.summary)}</p>
    <div class="ai-block"><h4>Hallazgos (${v.findings.length})</h4>${findings}</div>
    <div class="ai-block"><h4>Recomendaciones</h4>${v.recommendations.map((r) => `<div class="reco reco--${r.priority}">${esc(r.text)}</div>`).join("")}</div>
    <div class="ai-block"><h4>Factores de riesgo (modelo ML)</h4>${factors}</div>
    <div class="ai-block small muted mono">Validación #${v.id} · ${esc(v.created_at.replace("T", " "))}</div>
  </section>`;
}

/* ------------------------------------------------------------ phase form */
function fieldErrors(phase) {
  const map = {};
  (phase.last_validation?.findings || []).forEach((f) => {
    if (f.field && f.severity !== "info") (map[f.field] ||= []).push(f.message);
  });
  return map;
}

function requirementInput(req, phase, editable, errors) {
  const fields = phase.submission.fields || {};
  const docs = phase.submission.documents || {};
  const value = fields[req.key];
  const dis = editable ? "" : "disabled";
  const id = `f_${req.key}`;
  const err = errors[req.key];
  const errHtml = err ? `<span class="field__error">${esc(err[0])}</span>` : "";
  const cls = `field ${err ? "has-error" : ""}`;
  const hintParts = [];
  if (req.min_length) hintParts.push(`mín. ${req.min_length} caracteres`);
  if (req.min != null && req.max != null) hintParts.push(`entre ${req.min} y ${req.max}`);
  if (req.extensions) hintParts.push(req.extensions.join(", "));
  const hint = hintParts.length ? ` <span class="field__hint">· ${esc(hintParts.join(" · "))}</span>` : "";
  const req_ = req.required ? ' <span aria-hidden="true" style="color:var(--accent)">*</span>' : "";

  switch (req.type) {
    case "text": {
      const long = (req.min_length || 0) >= 50;
      const input = long
        ? `<textarea id="${id}" data-key="${req.key}" data-type="text" ${dis}>${esc(value)}</textarea>`
        : `<input id="${id}" type="text" data-key="${req.key}" data-type="text" value="${esc(value)}" ${dis}>`;
      return `<label class="${cls}" for="${id}"><span>${esc(req.label)}${req_}${hint}</span>${input}${errHtml}</label>`;
    }
    case "number":
      return `<label class="${cls}" for="${id}"><span>${esc(req.label)}${req_}${hint}</span>
        <input id="${id}" type="number" step="any" data-key="${req.key}" data-type="number" value="${esc(value)}" ${dis}>${errHtml}</label>`;
    case "date":
      return `<label class="${cls}" for="${id}"><span>${esc(req.label)}${req_}</span>
        <input id="${id}" type="date" data-key="${req.key}" data-type="date" value="${esc(value)}" ${dis}>${errHtml}</label>`;
    case "select":
      return `<label class="${cls}" for="${id}"><span>${esc(req.label)}${req_}</span>
        <select id="${id}" data-key="${req.key}" data-type="select" ${dis}><option value="">Seleccione…</option>
        ${req.options.map((o) => `<option ${o === value ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>${errHtml}</label>`;
    case "checklist":
      return `<div class="${cls}"><label class="check"><input type="checkbox" data-key="${req.key}" data-type="checklist" ${value ? "checked" : ""} ${dis}>
        <span>${esc(req.label)}${req_}</span></label>${errHtml}</div>`;
    case "document": {
      const doc = docs[req.key];
      return `<div class="${cls}" style="font-size:13px;font-weight:500"><span>${esc(req.label)}${req_}${hint}</span>
        <div class="doc-row">
          <span class="${doc ? "doc-row__file" : "muted small"}">${doc ? `✓ ${esc(doc.filename)} · ${doc.size < 1024 ? doc.size + " B" : (doc.size / 1024).toFixed(1) + " KB"}` : "Sin archivo adjunto"}</span>
          ${editable ? `<input type="file" aria-label="Adjuntar ${esc(req.label)}" data-doc="${req.key}" accept="${esc((req.extensions || []).join(","))}">` : ""}
        </div>${errHtml}</div>`;
    }
    default:
      return "";
  }
}

function collectFields(form) {
  const fields = {};
  form.querySelectorAll("[data-key]").forEach((el) => {
    const t = el.dataset.type;
    if (t === "checklist") fields[el.dataset.key] = el.checked;
    else if (t === "number") fields[el.dataset.key] = el.value === "" ? null : Number(el.value);
    else fields[el.dataset.key] = el.value;
  });
  return fields;
}

/* ================================================================== VIEWS */
async function viewDashboard() {
  const d = await api("/api/dashboard");
  const processes = await api("/api/processes");
  const k = d.kpis;
  mainEl.innerHTML = `
    ${pageHead("Supervisión continua", "Cada fase, validada<br>antes de avanzar.",
      "La IA verifica requisitos, detecta retrasos e inconsistencias y recomienda acciones en cada etapa del proceso.",
      `<a class="btn btn--primary" href="#/new">Nuevo proceso →</a>`)}
    <div class="kpis fade-in">
      ${kpi("Procesos", k.total, `${k.completed} finalizados`)}
      ${kpi("Activos", k.active, "en ejecución")}
      ${kpi("Bloqueados", k.blocked, "por la IA", k.blocked ? "kpi--err" : "")}
      ${kpi("Vencidos", k.overdue, "fase fuera de plazo", k.overdue ? "kpi--warn" : "")}
      ${kpi("Alertas", k.open_alerts, `${k.critical_alerts} críticas`, k.critical_alerts ? "kpi--err" : "")}
    </div>

    <div class="section grid-2">
      <section class="panel" aria-labelledby="risk-title">
        <div class="panel__head"><h2 id="risk-title" class="panel__title">Procesos con riesgo de retraso</h2>
          <span class="small muted mono">modelo ML</span></div>
        ${d.at_risk.length ? `<div class="table-wrap"><table><tbody>${d.at_risk.map((p) => `
          <tr><td><a class="row-link" href="#/process/${p.id}">${esc(p.name)}</a>
            <div class="small muted">Fase: ${esc(p.current_phase)}</div></td>
            <td style="width:40%">${bar(p.current_risk, true)}</td>
            <td class="num">${tag(fmtPct(p.current_risk), TONE[riskLevel(p.current_risk)])}</td></tr>`).join("")}</tbody></table></div>`
          : emptyState("Sin procesos en riesgo", "Ningún proceso supera el 40% de probabilidad de retraso.")}
      </section>
      <section class="panel" aria-labelledby="alerts-title">
        <div class="panel__head"><h2 id="alerts-title" class="panel__title">Alertas recientes</h2>
          <a class="small" href="#/alerts">Ver todas →</a></div>
        ${alertList(d.recent_alerts.slice(0, 6))}
      </section>
    </div>

    <section class="section" aria-labelledby="proc-title">
      <div class="section__head"><h2 id="proc-title" class="section__title">Procesos</h2>
        <a class="small" href="#/processes">Ver listado →</a></div>
      <div class="panel">${processTable(processes)}</div>
    </section>`;
}

async function viewProcesses(params) {
  const filter = params.get("category") || "";
  const processes = await api(`/api/processes${filter ? `?category=${filter}` : ""}`);
  const chip = (value, text) => `<a class="btn btn--sm ${filter === value ? "btn--primary" : ""}" href="#/processes${value ? `?category=${value}` : ""}">${text}</a>`;
  mainEl.innerHTML = `
    ${pageHead("Procesos", "Todos los procesos", "", `<a class="btn btn--primary" href="#/new">Nuevo proceso →</a>`)}
    <div class="form-actions" style="margin-bottom:24px" role="group" aria-label="Filtrar por tipo">
      ${chip("", "Todos")}${chip("academic", "Académicos")}${chip("administrative", "Administrativos")}${chip("business", "Empresariales")}
    </div>
    <div class="panel fade-in">${processTable(processes)}</div>`;
}

async function viewNew() {
  const templates = await api("/api/templates");
  let selected = templates[0].key;
  mainEl.innerHTML = `
    ${pageHead("Nuevo proceso", "Elija una plantilla", "Cada plantilla define las fases, los requisitos y las reglas que la IA verificará.")}
    <div class="grid-cards" role="group" aria-label="Plantillas">
      ${templates.map((t) => `
        <button class="tpl-card" data-tpl="${t.key}" aria-pressed="${t.key === selected}">
          <span class="eyebrow" style="margin:0">${esc(LABELS.category[t.category])}</span>
          <h3>${esc(t.name)}</h3><p class="muted small">${esc(t.description)}</p>
          <div class="tpl-phases">${t.phases.map((p, i) => tag(`${i + 1}. ${p.name} · ${p.planned_days}d`, "plain")).join("")}</div>
        </button>`).join("")}
    </div>
    <form id="new-form" class="panel section" novalidate>
      <div class="panel__head"><span class="panel__title">Datos del proceso</span></div>
      <div class="panel__body form-grid">
        <label class="field" for="n_name">Nombre del proceso<input id="n_name" name="name" type="text" required minlength="3" placeholder="Ej. Trabajo de grado — App de tutorías"></label>
        <label class="field" for="n_owner">Responsable<input id="n_owner" name="owner" type="text" required minlength="3" placeholder="Nombre completo"></label>
        <label class="field" for="n_start">Fecha de inicio<input id="n_start" name="start_date" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
        <label class="field" for="n_desc">Descripción <span class="field__hint">· opcional</span><textarea id="n_desc" name="description"></textarea></label>
        <div class="form-actions"><button class="btn btn--primary" type="submit" data-loading="Creando…">Crear proceso →</button>
          <a class="btn" href="#/">Cancelar</a></div>
      </div>
    </form>`;

  mainEl.querySelectorAll("[data-tpl]").forEach((btn) => btn.addEventListener("click", () => {
    selected = btn.dataset.tpl;
    mainEl.querySelectorAll("[data-tpl]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.tpl === selected));
  }));

  const form = document.getElementById("new-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    form.querySelectorAll(".field").forEach((f) => { f.classList.remove("has-error"); f.querySelector(".field__error")?.remove(); });
    let valid = true;
    ["name", "owner"].forEach((k) => {
      if ((data[k] || "").trim().length < 3) {
        valid = false;
        const label = form.querySelector(`[name=${k}]`).closest(".field");
        label.classList.add("has-error");
        label.insertAdjacentHTML("beforeend", `<span class="field__error">Escriba al menos 3 caracteres.</span>`);
      }
    });
    if (!valid) return;
    await withLoading(e.submitter, async () => {
      try {
        const p = await api("/api/processes", { method: "POST", json: { ...data, template_key: selected, start_date: data.start_date || null } });
        toast("Proceso creado. La fase 1 está en curso.", "ok");
        location.hash = `#/process/${p.id}`;
      } catch (err) { toast(err.message, "err"); }
    });
  });
}

async function viewProcess(id, params) {
  const p = await api(`/api/processes/${id}`);
  const active = p.phases.find((ph) => ph.order === p.current_phase_order);
  const selectedOrder = Number(params.get("phase")) || active?.order || 1;
  const phase = p.phases.find((ph) => ph.order === selectedOrder) || active;
  const editable = p.status !== "completed" && ["in_progress", "blocked"].includes(phase.status);
  const errors = editable ? fieldErrors(phase) : {};
  const phaseAlerts = p.alerts.filter((a) => !a.resolved);

  mainEl.innerHTML = `
    ${pageHead(`${LABELS.category[p.category]} · Responsable: ${p.owner}`, esc(p.name),
      `${statusTag(p.status)} &nbsp; Avance ${Math.round(p.progress)}% · Iniciado ${fmtDate(p.start_date)}`,
      `<a class="btn" href="/api/processes/${p.id}/report.html" target="_blank" rel="noopener">Reporte de cumplimiento ↗</a>`)}

    <ol class="stepper" aria-label="Fases del proceso">
      ${p.phases.map((ph) => `<li><button class="step is-${ph.status} ${ph.order === phase.order ? "is-selected" : ""}" data-phase="${ph.order}"
          aria-current="${ph.order === phase.order ? "step" : "false"}" style="width:100%">
        <span class="step__num">FASE ${ph.order}</span><span class="step__name">${esc(ph.name)}</span>
        <span class="step__meta">${esc(LABELS.phaseStatus[ph.status])}${ph.last_score != null ? ` · ${Math.round(ph.last_score)} pts` : ""}${ph.due_date && ph.status !== "approved" ? ` · vence ${fmtDate(ph.due_date)}` : ""}</span>
      </button></li>`).join("")}
    </ol>

    <div class="workspace">
      <form id="phase-form" class="panel" novalidate>
        <div class="panel__head">
          <div><div class="panel__title">Fase ${phase.order}: ${esc(phase.name)}</div>
            <div class="small muted">${esc(phase.description)}</div></div>
          ${statusTag(phase.status, LABELS.phaseStatus)}
        </div>
        <div class="panel__body form-grid">
          <div class="small muted mono">Plazo: ${phase.planned_days} días · Inicio ${fmtDate(phase.start_date)} · Límite ${fmtDate(phase.due_date)}${phase.completed_at ? ` · Cerrada ${fmtDate(phase.completed_at)}` : ""} · Rechazos: ${phase.rejections}</div>
          ${phase.status === "pending" ? emptyState("Fase pendiente", "Se habilitará cuando la IA apruebe la fase anterior.") :
            phase.requirements.map((r) => requirementInput(r, phase, editable, errors)).join("")}
          ${editable ? `<div class="form-actions">
            <button type="button" class="btn" id="btn-save" data-loading="Guardando…">Guardar</button>
            <button type="button" class="btn" id="btn-validate" data-loading="Analizando…">Validar con IA</button>
            <button type="button" class="btn btn--primary" id="btn-advance" data-loading="Verificando…">Avanzar a la siguiente fase →</button>
          </div>` : ""}
        </div>
      </form>
      <div>${aiPanel(phase.last_validation)}</div>
    </div>

    <section class="section" aria-labelledby="pa-title">
      <div class="section__head"><h2 id="pa-title" class="section__title">Alertas del proceso</h2>
        <span class="small muted">${phaseAlerts.length} abiertas</span></div>
      <div class="panel">${alertList(phaseAlerts, { showProcess: false, resolvable: true })}</div>
    </section>`;

  mainEl.querySelectorAll("[data-phase]").forEach((b) => b.addEventListener("click", () => {
    location.hash = `#/process/${p.id}?phase=${b.dataset.phase}`;
  }));
  bindResolveButtons(() => viewProcess(id, params));
  if (!editable) return;

  const form = document.getElementById("phase-form");
  const save = () => api(`/api/phases/${phase.id}/submission`, { method: "PUT", json: { fields: collectFields(form) } });
  const reload = () => viewProcess(id, params);

  document.getElementById("btn-save").addEventListener("click", (e) => withLoading(e.currentTarget, async () => {
    try { await save(); toast("Cambios guardados.", "ok"); } catch (err) { toast(err.message, "err"); }
  }));

  document.getElementById("btn-validate").addEventListener("click", (e) => withLoading(e.currentTarget, async () => {
    try {
      await save();
      const v = await api(`/api/phases/${phase.id}/validate`, { method: "POST" });
      toast(v.passed ? "La IA validó la fase." : "La IA encontró problemas en la fase.", v.passed ? "ok" : "err");
      await reload();
    } catch (err) { toast(err.message, "err"); }
  }));

  document.getElementById("btn-advance").addEventListener("click", (e) => withLoading(e.currentTarget, async () => {
    try {
      await save();
      const r = await api(`/api/phases/${phase.id}/advance`, { method: "POST" });
      if (r.advanced) {
        toast(r.process.status === "completed" ? "Proceso finalizado." : "Fase aprobada por la IA. Siguiente fase en curso.", "ok");
        location.hash = `#/process/${p.id}`;
        if (!params.get("phase")) await reload();
      } else {
        toast("La IA bloqueó el avance: revise los hallazgos.", "err");
        await reload();
      }
    } catch (err) { toast(err.message, "err"); }
  }));

  form.querySelectorAll("[data-doc]").forEach((input) => input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      await save();
      const body = new FormData();
      body.append("key", input.dataset.doc);
      body.append("file", file);
      await api(`/api/phases/${phase.id}/documents`, { method: "POST", body });
      toast(`Documento «${file.name}» adjuntado.`, "ok");
      await reload();
    } catch (err) { toast(err.message, "err"); }
  }));
}

async function viewAlerts(params) {
  const showResolved = params.get("resolved") === "1";
  const alerts = await api(`/api/alerts?resolved=${showResolved}`);
  mainEl.innerHTML = `
    ${pageHead("Alertas", showResolved ? "Alertas resueltas" : "Alertas abiertas",
      "Generadas por la IA al validar fases y por el monitor de plazos.",
      `<a class="btn" href="#/alerts${showResolved ? "" : "?resolved=1"}">${showResolved ? "Ver abiertas" : "Ver resueltas"}</a>`)}
    <div class="panel fade-in">${alertList(alerts, { resolvable: !showResolved })}</div>`;
  bindResolveButtons(() => viewAlerts(params));
}

async function viewAI() {
  const m = await api("/api/ai/model");
  const maxCoef = Math.max(...Object.values(m.coefficients).map(Math.abs));
  const FEATURE_ES = {
    completion_ratio: "Cumplimiento de requisitos", time_ratio: "Tiempo consumido / planeado",
    rejections: "Rechazos previos", prev_delay_days: "Retraso acumulado", phase_position: "Posición de la fase",
    error_count: "Errores bloqueantes",
  };
  mainEl.innerHTML = `
    ${pageHead("Motor de IA", "Supervisión híbrida", "Un motor de reglas verifica lo que debe cumplirse; un modelo de aprendizaje automático estima lo que podría salir mal.")}
    <div class="kpis fade-in">
      ${kpi("Exactitud", fmtPct(m.accuracy), "conjunto de prueba")}
      ${kpi("ROC AUC", m.roc_auc.toFixed(3), "capacidad de discriminación")}
      ${kpi("Entrenamiento", m.training_samples.toLocaleString("es-CO"), "ejecuciones de fase")}
      ${kpi("Prueba", m.test_samples.toLocaleString("es-CO"), "ejecuciones de fase")}
      ${kpi("Tasa de retraso", fmtPct(m.delay_rate), "en el histórico")}
    </div>
    <div class="section grid-2">
      <section class="panel"><div class="panel__head"><h2 class="panel__title">Peso de cada variable</h2><span class="small muted mono">coeficientes estandarizados</span></div>
        <div class="panel__body">${Object.entries(m.coefficients).map(([f, c]) => `
          <div class="factor" style="grid-template-columns:1fr 140px 56px">
            <span>${esc(FEATURE_ES[f])}</span>${bar(Math.abs(c) / maxCoef, c > 0)}
            <span class="mono small" style="text-align:right">${c > 0 ? "+" : ""}${c.toFixed(2)}</span></div>`).join("")}
          <p class="small muted" style="margin-top:12px">Positivo (ámbar) aumenta el riesgo de retraso; negativo lo reduce.</p></div>
      </section>
      <section class="panel"><div class="panel__head"><h2 class="panel__title">Flujo de validación</h2></div>
        <div class="panel__body"><div class="code">Evidencias de la fase
   │
   ├─► Motor de reglas ── requisitos, documentos,
   │                      consistencia entre fases,
   │                      plazos, calidad del texto
   │
   ├─► Modelo ML ──────── probabilidad de retraso
   │                      + factores explicativos
   ▼
Puntaje 0–100 · Decisión · Alertas · Recomendaciones
   │
   └─► ¿Sin errores y puntaje ≥ 70? ── sí ─► Avanza
                                      no ─► Bloquea</div>
        <p class="small muted" style="margin-top:12px">Algoritmo: ${esc(m.algorithm)}. Datos: ${esc(m.data_source)}.</p></div>
      </section>
    </div>`;
}

function bindResolveButtons(refresh) {
  mainEl.querySelectorAll("[data-resolve]").forEach((b) => b.addEventListener("click", () => withLoading(b, async () => {
    try { await api(`/api/alerts/${b.dataset.resolve}/resolve`, { method: "POST" }); toast("Alerta marcada como resuelta.", "ok"); await refresh(); }
    catch (err) { toast(err.message, "err"); }
  })));
}

/* ================================================================= ROUTER */
async function updateAlertBadge() {
  try {
    const alerts = await api("/api/alerts");
    const critical = alerts.filter((a) => a.level === "critical").length;
    const el = document.getElementById("nav-alerts");
    el.hidden = critical === 0;
    el.textContent = critical;
  } catch (_) { /* ignore */ }
}

async function router() {
  const [path, query = ""] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(query);
  const parts = path.split("/").filter(Boolean);
  const route = parts[0] || "dashboard";

  document.querySelectorAll("[data-route]").forEach((a) => a.classList.toggle("is-active",
    a.dataset.route === route || (route === "process" && a.dataset.route === "processes")));
  document.getElementById("main-nav").classList.remove("is-open");
  document.querySelector(".nav-toggle").setAttribute("aria-expanded", "false");

  window.scrollTo(0, 0);
  mainEl.innerHTML = `<div class="loading" role="status"><div class="skeleton" style="width:40%;margin:0 auto 12px"></div>Cargando…</div>`;
  try {
    if (route === "dashboard") await viewDashboard();
    else if (route === "processes") await viewProcesses(params);
    else if (route === "new") await viewNew();
    else if (route === "process") await viewProcess(parts[1], params);
    else if (route === "alerts") await viewAlerts(params);
    else if (route === "ai") await viewAI();
    else mainEl.innerHTML = emptyState("Página no encontrada", "La ruta solicitada no existe.", `<a class="btn" href="#/">Ir al panel</a>`);
  } catch (err) {
    mainEl.innerHTML = `<div class="panel" style="margin-top:48px">${emptyState("Algo salió mal", `No se pudo cargar la información: ${err.message}`,
      `<button class="btn" onclick="router()">Reintentar</button>`)}</div>`;
  }
  updateAlertBadge();
}

document.querySelector(".nav-toggle").addEventListener("click", (e) => {
  const nav = document.getElementById("main-nav");
  const open = nav.classList.toggle("is-open");
  e.currentTarget.setAttribute("aria-expanded", String(open));
});
window.addEventListener("hashchange", router);
router();
