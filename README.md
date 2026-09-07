# Plataforma de Gestión del Módulo Habitar (CPU - UNSAM)

MVP del Trabajo Práctico Final Integrador. **Grupo 10** (Ingeniería de Software, 1C 2026).

Plataforma web que centraliza la gestión del Módulo Habitar del CPU: reemplaza el proceso
manual (Google Forms + planillas de papel + revisión de fotos) por inscripción digital,
acreditación de asistencia por **código QR** y seguimiento de créditos.

## Demo en vivo

> **https://habitar-cpu.onrender.com**

Guía completa de acceso y testeo: [`docs/Instrucciones_Demo_y_QC.md`](docs/Instrucciones_Demo_y_QC.md).
Primer acceso: el plan gratuito hiberna; puede demorar ~30-50 s en reactivarse.

Cuentas de prueba (contraseña `habitar123`): `ana@alumno.unsam.edu.ar` (estudiante),
`coordinacion@unsam.edu.ar`, `docente@unsam.edu.ar`, `director@unsam.edu.ar`.
Alta de estudiante nuevo: usar un legajo del padrón demo (`1003`-`1008`, `2001`, `2002`).

## Stack
- **Backend:** FastAPI + SQLAlchemy 2 + Jinja2 (Python 3.13)
- **DB:** PostgreSQL (Neon)
- **Frontend:** Jinja2 + Tailwind (CDN) + Chart.js + html5-qrcode
- **Jobs:** APScheduler (recordatorios 24 h)
- **Deploy:** Docker + Render (blueprint en `render.yaml`)

## Funcionalidad (10 épicas, profundidad MVP)
| Épica | Implementado |
|---|---|
| E-01 Autenticación y perfil | Signup con verificación de legajo (SIU mock), login, roles, perfil |
| E-02 Descubrimiento | Listado + filtros (fecha/tipo/créditos/cupo), detalle |
| E-03 Inscripción | Inscripción 1-click, **control de cupo transaccional**, baja, confirmación mail+in-app |
| E-04 Recordatorios | "Mis próximas actividades", recordatorio 24 h por mail, FAQ editable |
| E-05 Asistencia QR | Sesión con QR/código rotativo del docente; check-in del estudiante validado |
| E-06 Encuesta | Encuesta de satisfacción post-asistencia |
| E-07 Progreso | Créditos acumulados, barra de progreso, historial |
| E-08 Gestión de actividades | ABM, vista previa, publicar, editar→notifica inscriptos |
| E-09 Inscriptos y asistencia | Listado, validación, **export CSV/XLSX**, import de padrón |
| E-10 Analítica | Dashboard (tasa de asistencia, top actividades, encuestas) |

## Roles y cuentas demo (contraseña `habitar123`)
| Rol | Email |
|---|---|
| Estudiante | `ana@alumno.unsam.edu.ar` |
| Coordinación (admin) | `coordinacion@unsam.edu.ar` |
| Docente | `docente@unsam.edu.ar` |
| Director de carrera | `director@unsam.edu.ar` |

Para registrarte como estudiante nuevo usá un legajo del padrón demo: `1003`-`1008`.

## Correr localmente
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # completá DATABASE_URL (Neon) y SECRET_KEY
uvicorn app.main:app --reload
# http://localhost:8000
```
Al iniciar crea las tablas (`create_all`) y siembra datos demo de forma idempotente.

## Deploy en Render (blueprint)
1. Push de este repo a GitHub.
2. En Render → **New → Blueprint** → conectá el repo (detecta `render.yaml`).
3. Setear la variable **`DATABASE_URL`** con la connection string de Neon
   (`SECRET_KEY` se autogenera).
4. Deploy → la app queda en `https://<servicio>.onrender.com`.

> Plan free: el servicio hiberna tras inactividad (~30 s de arranque en frío).

## Arquitectura
Estilos y patrones de diseño con referencias al código: [`docs/Arquitectura_y_Patrones.md`](docs/Arquitectura_y_Patrones.md).

Capas jerárquicas: `routers/` (páginas Jinja + endpoints) → `services/` (dominio:
identity, actividades, enrollment, asistencia, credits, analytics) → `models.py` (ORM) → Postgres.

```
app/
  main.py        wiring, middleware, lifespan (create_all + seed + scheduler)
  models.py      modelos ORM
  security.py    hashing bcrypt, sesiones, guards por rol
  services/      lógica de dominio
  routers/       auth, discovery, enrollment, asistencia, admin_*, analytics, faq
  templates/     Jinja2
```

## Decisiones de MVP (divergen del whitepaper, documentadas)
- **SIU Guaraní** → simulador: tabla `valid_legajos` sembrada (único punto de swap en `services/identity.py`).
- **Redis Pub/Sub** → notificaciones in-app + mail (tabla `notifications`).
- **Dash/Plotly** → Chart.js renderizado en el servidor.
- **Migraciones** → `Base.metadata.create_all` al iniciar (single service).

## Notas de seguridad para producción
- Contraseñas con **bcrypt**, sesiones en cookie firmada, acceso por rol.
- `SECRET_KEY` débil/placeholder se rechaza (clave efímera + aviso); en Render se autogenera.
- Cookie de sesión `Secure` en producción (`SESSION_HTTPS_ONLY=1` en `render.yaml`) y `SameSite=Lax`.
- Cupo resuelto con `SELECT ... FOR UPDATE` (sin sobre-inscripción en carreras).
- Asistencia auditable (`validated_by` + `validated_at`).
- **Hardening pendiente:** tokens anti-CSRF en los formularios POST (hoy solo `SameSite=Lax`);
  política de zona horaria única (hoy las fechas se guardan como hora local etiquetada UTC);
  `INSERT ... ON CONFLICT` en la importación de
  legajos para no descartar el lote ante una colisión concurrente; compilar Tailwind (hoy CDN)
  y agregar `integrity`/SRI a los `<script>` de CDN (Chart.js, html5-qrcode).
