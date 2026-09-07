# Plataforma de Gestión del Módulo Habitar (CPU - UNSAM). MVP Design

**Date:** 2026-06-15, **Group 10**, Source: `Whitepaper_Grupo10.docx.pdf`

## Goal
Replace the manual (Google Forms + paper asistencia + photo review) process for the
"Módulo Habitar" CPU onboarding course with a single web platform, deployed live.
MVP depth across all 10 epics.

## Decisions (locked)
- **Stack:** FastAPI + SQLAlchemy 2 + Jinja2 + Neon Postgres (whitepaper-aligned).
- **Scope:** all 10 epics at MVP depth.
- **SIU Guaraní:** mocked via a seeded `valid_legajos` table.
- **Deploy:** GitHub repo + Render blueprint (`render.yaml` + Dockerfile), Neon Postgres.

## Divergences from whitepaper (intentional, MVP)
- Redis Pub/Sub broker → collapsed to in-process notify + `notifications` table.
- Dash/Plotly separate service → Chart.js server-rendered in Jinja.
- Alembic migrations → `Base.metadata.create_all()` on startup (single service, MVP).
- SIU Guaraní live integration → seeded simulator table.
Each is a smaller surface for a reliable single-service live deploy; swap-in points kept clean.

## Architecture
Hierarchical Layers: Routers (Jinja pages + JSON endpoints) → Services (domain) →
SQLAlchemy models → Neon Postgres. Single Dockerized FastAPI service.

```
app/
  main.py          FastAPI app, SessionMiddleware, router includes, startup (create_all, seed, scheduler)
  config.py        Settings (DATABASE_URL, SECRET_KEY, SMTP, REQUIRED_CREDITS)
  database.py      engine, SessionLocal, Base, get_db
  models.py        all ORM models
  security.py      bcrypt hashing, session cookie, current_user deps, rol guards
  email_util.py    email backend: SMTP if configured else console/log
  notifications.py in-app + email notify service
  scheduler.py     APScheduler, 24h reminders
  seed.py          seed valid_legajos, staff users, demo actividades, faq, config
  services/        identity, actividades, enrollment, asistencia, credits, analytics
  routers/         auth, discovery, enrollment, asistencia, admin_actividades, admin_enroll, analytics, faq
  templates/       base + per-area Jinja
  static/          app.js
```

## Roles
`estudiante` (self-signup, legajo verified), `coordinacion` (admin, seeded),
`docente` (seeded, validates asistencia), `director` (seeded, read-only analytics).

## Data model
- **users**(id, legajo, email unique, pw_hash, nombre, apellido, dni, carrera, rol, created_at)
- **valid_legajos**(legajo PK, nombre), SIU mock; signup must match
- **actividades**(id, titulo, descripcion, tipo[presencial|virtual], fecha_inicio, fecha_fin, lugar, docente_id→users, creditos, cupo_max, estado[borrador|publicada|cancelada], created_by, created_at)
- **inscripciones**(id, actividad_id, user_id, estado[inscripto|baja], created_at), unique active (actividad,user); cupo enforced **transactionally** (row lock on actividad)
- **sesiones_asistencia**(id, actividad_id, token, expires_at, created_by), rotating token for QR
- **asistencia**(id, actividad_id, user_id, validated_by→users, validated_at), unique (actividad,user); audit trail
- **survey_responses**(id, actividad_id, user_id, rating 1-5, comment, created_at)
- **faq**(id, pregunta, respuesta, orden)
- **notifications**(id, user_id, mensaje, leido, created_at)
- **app_config**(key PK, value), holds `required_credits`

## Epic behaviour (MVP depth)
- **E-01 Auth:** signup(legajo∈valid_legajos)→estudiante; login/logout; min profile; rol guards. Staff seeded.
- **E-02 Discovery:** calendar + list of `publicada` actividades; filters fecha/tipo/créditos/cupo-disponible; detail page.
- **E-03 Inscription:** 1-click inscribir w/ transactional cupo check; unenroll frees cupo; email + in-app confirm.
- **E-04 Reminders:** "Mis próximas actividades" on home; APScheduler job emails enrolled 24h before start; admin-editable FAQ.
- **E-05 QR asistencia:** docente opens asistencia session → rotating QR + 6-digit code; student scans/enters in-app → validate(token live + enrolled + not already present) → mark present (validated_by=docente).
- **E-06 Survey:** optional 1-5 + comment after asistencia; stored per (actividad,user).
- **E-07 Progress:** accumulated credits (sum creditos where present), progress bar vs `required_credits`, completed-actividad history.
- **E-08 Admin actividades:** CRUD, preview, publish, edit published → notify enrolled (email+in-app), pending list.
- **E-09 Admin inscribir/asistencia:** inscriptos list per actividad, asistencia supervision, CSV/XLSX export of inscriptos, CSV import of valid_legajos.
- **E-10 Analytics:** dashboard (asistencia rate, top actividades by enrollment, enrollment summary, survey averages) via Chart.js; director read-only.

## Non-functional (whitepaper attributes)
- **Security:** rol-based access, bcrypt passwords, signed session cookies.
- **Reliability:** cupo race resolved by `SELECT ... FOR UPDATE` on actividad row inside inscribir txn.
- **Auditability:** asistencia rows carry validated_by + validated_at.
- **Interoperability:** SIU lookup isolated behind `services/identity.py` (one swap point).
- **Usability:** server-rendered, Tailwind CDN, minimal JS.

## Deploy plan
1. Neon Postgres provisioned (project `lively-bonus-85365036`). ✓
2. Build app, `Base.metadata.create_all` + idempotent seed on startup.
3. Dockerfile (python:3.13-slim, uvicorn) + `render.yaml` blueprint (web service, DATABASE_URL + SECRET_KEY env).
4. Run locally (uvicorn) → verify happy paths.
5. Push to GitHub (account korentomas); user connects repo in Render → live URL.

## Demo seed
valid_legajos sample; one user per rol (coordinacion/docente/director + a couple estudiantes);
a few publicada actividades across dates; FAQ entries; required_credits.

## Out of scope (MVP)
Real SIU integration, Redis broker, Dash, push notifications, multi-campus, i18n.
