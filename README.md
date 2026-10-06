# ProcesIA — Sistema de seguimiento de procesos con IA

Plataforma que acompaña un proceso desde su inicio hasta su finalización, fase por fase.
En cada fase un **supervisor de IA** verifica que se cumplan los requisitos establecidos,
detecta errores, retrasos e inconsistencias, genera alertas y recomendaciones, y **no deja
avanzar el proceso** hasta que la fase cumpla. También genera reportes automáticos de cumplimiento.

Se adapta a procesos **académicos, administrativos y empresariales** mediante plantillas.

> **Estado: prototipo funcional v0.5 — avance del 50 %.**

---

## 1. Ejecución rápida

```bash
pip install -r requirements.txt
python run.py
```

Abra **http://127.0.0.1:8000** (interfaz) o **http://127.0.0.1:8000/docs** (API interactiva / Swagger).

**Anaconda / Spyder:** abra `run.py` y ejecútelo con F5 (instale antes las dependencias desde
Anaconda Prompt con `pip install -r requirements.txt`). Para detener el servidor, reinicie el kernel.

Al iniciar por primera vez se crea `data/processes.db` con **4 procesos de demostración** en estados
distintos (uno bloqueado por la IA, uno con fase en curso y observaciones, uno finalizado y uno recién
creado). Para empezar desde cero borre `data/processes.db`, o ejecute con `SEED_DEMO=0`.

Pruebas automáticas:

```bash
python -m pytest -q        # 11 pruebas (motor de reglas, modelo ML y flujo completo de la API)
```

---

## 2. Alcance del avance (50 %)

| # | Módulo | Estado | Peso |
|---|--------|--------|------|
| 1 | Modelo de datos (procesos, fases, validaciones, alertas) + API REST | ✅ Completo | 10 % |
| 2 | Plantillas configurables (académico, administrativo, empresarial) | ✅ Completo (3 plantillas en código) | 5 % |
| 3 | Ciclo de vida del proceso y **compuerta de IA** para avanzar de fase | ✅ Completo | 10 % |
| 4 | Registro de evidencias: campos y carga de documentos | ✅ Completo | 5 % |
| 5 | **Motor de reglas** (requisitos, documentos, consistencia entre fases, plazos, calidad de texto) | ✅ Completo | 8 % |
| 6 | **Modelo ML de riesgo de retraso** explicable | ✅ Completo (entrenado con histórico sintético) | 5 % |
| 7 | Alertas automáticas y recomendaciones | ✅ Completo | 4 % |
| 8 | Reporte automático de cumplimiento (HTML imprimible / PDF del navegador) | ✅ Básico | 3 % |
| 9 | Interfaz web (panel, procesos, fase, alertas, motor IA) | 🟡 Parcial | — |
| | **Subtotal implementado** | | **50 %** |
| 10 | Autenticación, usuarios y roles (responsable, revisor, administrador) | ⏳ Pendiente | 10 % |
| 11 | Editor visual de plantillas (crear procesos propios sin programar) | ⏳ Pendiente | 8 % |
| 12 | Entrenamiento del modelo con el histórico real de la plataforma | ⏳ Pendiente | 7 % |
| 13 | Análisis de contenido de documentos (extracción de texto PDF/DOCX + NLP / LLM opcional) | ⏳ Pendiente | 8 % |
| 14 | Notificaciones (correo) y monitor programado de plazos | ⏳ Pendiente | 5 % |
| 15 | Reportes avanzados: exportación PDF/Excel, consolidado por área, programación | ⏳ Pendiente | 5 % |
| 16 | Bitácora de auditoría, despliegue (Docker) y pruebas de usabilidad | ⏳ Pendiente | 7 % |

---

## 3. Arquitectura

```
┌──────────────────────── Navegador ────────────────────────┐
│  static/  index.html · styles.css · app.js  (SPA, hash)   │
└───────────────┬───────────────────────────────────────────┘
                │ JSON / multipart
┌───────────────▼──────────── FastAPI (app/) ───────────────┐
│ routers/   processes · phases · general                   │
│ services/  process_service  ── ciclo de vida + compuerta  │
│            alert_service    ── alertas sin duplicados     │
│            monitor_service  ── detección de vencimientos  │
│            report_service   ── reporte de cumplimiento    │
│ ai/        supervisor ─┬─ rules_engine  (determinista)    │
│                        ├─ risk_model    (scikit-learn)    │
│                        └─ recommender   (acciones)        │
│ catalog.py plantillas de procesos, requisitos y reglas    │
└───────────────┬───────────────────────────────────────────┘
                │ SQLAlchemy
          SQLite (data/processes.db) · data/uploads/
```

### Flujo de una fase

```
Evidencias (campos + documentos)
   │
   ├─► Motor de reglas ──► hallazgos: error / advertencia / info
   ├─► Modelo ML ───────► probabilidad de retraso + factores
   ▼
Puntaje 0–100 · resumen · recomendaciones · alertas
   │
   └─► Avanzar fase:  ¿sin errores y puntaje ≥ 70?  sí → fase Cumplida, siguiente En curso
                                                     no → fase y proceso Bloqueados
```

---

## 4. El supervisor de IA

Es **híbrido**: combina conocimiento experto explícito (reglas) con aprendizaje automático.

### 4.1 Motor de reglas (`app/ai/rules_engine.py`)

| Verificación | Ejemplo |
|---|---|
| Requisitos obligatorios y tipos | texto con longitud mínima, número en rango, fecha válida, opción permitida, casilla confirmada |
| Documentos soporte | presencia, extensión permitida, archivo no vacío |
| Consistencia dentro de la fase | fecha de inicio ≤ fecha de fin |
| **Consistencia entre fases** | valor cotizado (fase 2) ≤ presupuesto (fase 1); valor aprobado = valor cotizado; entrega posterior a la aprobación |
| Plazos | vencida → advertencia (no bloquea, para que la fase pueda cerrarse); > 7 días → alerta crítica y −10 puntos; ≥ 80 % del tiempo → aviso |
| Calidad del contenido | texto provisional («lorem», «tbd», «por definir»…) o muy repetitivo |

Las reglas se declaran en las plantillas (`app/catalog.py`) con referencias `"fase.campo"`, p. ej.
`{"type": "max_ref", "field": "quoted_amount", "ref": "1.budget"}`.

**Puntaje:** `100 × requisitos cumplidos / total` − 15 por inconsistencia − 10 por vencimiento mayor a 7 días − 5 por advertencia.

### 4.2 Modelo de riesgo de retraso (`app/ai/risk_model.py`)

- Algoritmo: **regresión logística** con estandarización (scikit-learn). Se eligió por ser **explicable**:
  la contribución de cada variable se muestra al usuario como «factores de riesgo».
- Variables: cumplimiento de requisitos, tiempo consumido / planeado, rechazos previos,
  retraso acumulado de fases anteriores, posición de la fase y errores bloqueantes.
- Datos: 3 000 ejecuciones históricas **sintéticas** reproducibles (semilla 42), exportadas a
  `data/training_history.csv`. Métricas en la vista «Motor IA» o en `GET /api/ai/model`
  (exactitud ≈ 0,73; ROC AUC ≈ 0,82).
- Niveles: bajo < 40 % ≤ medio < 65 % ≤ alto.
- *Pendiente:* reentrenar con el histórico real a medida que la plataforma acumule procesos.

### 4.3 Recomendaciones (`app/ai/recommender.py`)

Traduce hallazgos y factores de riesgo en acciones concretas priorizadas (alta / media / baja).

---

## 5. API REST principal

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/templates` | Plantillas disponibles |
| GET / POST | `/api/processes` | Listar (filtros `status`, `category`) / crear proceso |
| GET / DELETE | `/api/processes/{id}` | Detalle con fases y alertas / eliminar |
| GET | `/api/processes/{id}/report` · `/report.html` | Reporte de cumplimiento JSON / HTML |
| PUT | `/api/phases/{id}/submission` | Guardar campos de la fase |
| POST | `/api/phases/{id}/documents` | Adjuntar documento (`key`, `file`) |
| POST | `/api/phases/{id}/validate` | Validación con IA |
| POST | `/api/phases/{id}/advance` | Compuerta de IA: valida y avanza o bloquea |
| GET | `/api/phases/{id}/validations` | Historial de validaciones |
| GET | `/api/dashboard` | Indicadores, procesos en riesgo y alertas recientes |
| GET / POST | `/api/alerts` · `/api/alerts/{id}/resolve` | Alertas abiertas o resueltas / resolver |
| GET | `/api/ai/model` | Métricas y coeficientes del modelo |

---

## 6. Guion de demostración (5 minutos)

1. **Panel**: indicadores, proceso en riesgo (89 %) y alertas críticas.
2. **Compra de equipos de laboratorio** → fase *Cotizaciones* bloqueada: la IA detectó que el valor
   cotizado supera el presupuesto de la fase 1, que hay menos de 3 cotizaciones y que la fase está vencida.
   Corrija `Número de cotizaciones = 3` y `Valor cotizado = 44000000`, pulse **Validar con IA**:
   los errores desaparecen y solo queda la advertencia de vencimiento. Pulse **Avanzar** → la fase pasa a *Cumplida*.
3. **Lanzamiento de app móvil** (recién creado): intente **Avanzar** vacío → bloqueado. Diligencie,
   ponga una fecha de cierre anterior a la de inicio → inconsistencia. Corrija, adjunte un PDF y avance.
4. **Plataforma de tutorías con IA** → **Reporte de cumplimiento**: conclusiones automáticas y detalle por fase.
5. **Motor IA**: métricas del modelo y peso de cada variable.

---

## 7. Estructura

```
seguimiento-procesos-ia/
├── run.py                 # lanzador (terminal, VS Code o Spyder)
├── requirements.txt
├── app/
│   ├── main.py            # aplicación FastAPI
│   ├── config.py          # umbrales y rutas
│   ├── database.py · models.py · schemas.py
│   ├── catalog.py         # plantillas: fases, requisitos y reglas
│   ├── seed.py            # datos de demostración
│   ├── ai/                # supervisor, rules_engine, risk_model, recommender
│   ├── services/          # lógica de negocio, alertas, monitor, reportes
│   └── routers/           # endpoints REST
├── static/                # interfaz web
├── tests/                 # pytest
└── data/                  # base de datos, documentos y dataset (se crean al ejecutar)
```

Tecnologías: Python 3.10+, FastAPI, SQLAlchemy 2, SQLite, scikit-learn, HTML/CSS/JavaScript.
