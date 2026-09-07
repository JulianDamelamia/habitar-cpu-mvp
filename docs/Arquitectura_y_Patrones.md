# Arquitectura y patrones de diseño: correspondencia con el código

**Grupo 10.** Plataforma de Gestión del Módulo Habitar (CPU - UNSAM).

Este documento explica cómo los estilos arquitectónicos y los patrones de diseño declarados
en el whitepaper (sección 5) se materializan en el código de la demo. Para cada patrón se
indica dónde vive dentro de `app/`, citando el archivo y la función correspondiente, y se
aclaran las diferencias entre el diseño declarado y lo efectivamente construido en el MVP. La
taxonomía de estilos sigue la de la Clase 9 del curso (dataflow, sistemas distribuidos,
sistemas interactivos y sistemas basados en eventos).

---

## 1. Vista de capas

El sistema se organiza como una aplicación FastAPI única, estructurada en capas. Cada pedido
entra por el navegador, atraviesa el servidor web, se resuelve en un módulo de dominio y
termina en la base de datos, y la respuesta recorre el mismo camino en sentido inverso.

```
Navegador (HTML + Jinja)                 capa de presentación
        |
FastAPI: middleware de sesión            capa de servidor web
y guardas de autorización
        |
Routers  (app/routers/*.py)              controladores HTTP
        |
Servicios de dominio (app/services/*.py) lógica de negocio
        |
Modelos ORM (app/models.py)              capa de datos
        |
PostgreSQL (Neon)
```

---

## 2. Estilos arquitectónicos declarados

### 2.1. Hierarchical Layers (dataflow)

Las cuatro capas declaradas en el whitepaper (cliente, servidor web, backend y base de datos)
se corresponden con la estructura del paquete `app/`. Cada capa se comunica solo con la
contigua y tiene una responsabilidad única.

| Capa declarada | Dónde está en el código |
|---|---|
| Cliente | Plantillas Jinja en `app/templates/` y el helper `app/templating.py` |
| Servidor web | La aplicación y el middleware en `app/main.py`; las guardas en `app/security.py` |
| Backend (módulos de dominio) | `app/services/` (identity, actividades, enrollment, asistencia, credits, analytics) |
| Base de datos | Los modelos ORM en `app/models.py` sobre PostgreSQL, configurada en `app/database.py` |

Los routers (`app/routers/`) actúan como frontera entre el servidor web y el dominio: reciben
la petición, delegan en un servicio y devuelven una vista. Ningún router accede directamente a
la base de datos salvo a través de los servicios y del ORM, lo que mantiene la separación de
capas.

### 2.2. Pipes and Filters (dataflow)

Cada solicitud atraviesa una cadena de etapas independientes antes de llegar al dominio, tal
como se declaró en el whitepaper. La etapa de filtrado por autenticación es la más visible.

- El middleware de sesión se monta en `app/main.py` (`app.add_middleware(SessionMiddleware, ...)`)
  y reconstruye la identidad del usuario a partir de la cookie firmada.
- El filtro de autorización es la dependencia `current_user_required` y la fábrica de guardas
  `require_roles(*roles)` en `app/security.py`. Cada endpoint declara con `Depends(...)` qué
  filtro debe atravesar antes de ejecutarse.
- Cuando un filtro rechaza la petición, las excepciones `NotAuthenticated` y `NotAuthorized`
  (definidas en `app/security.py`) se transforman en redirección o en una pantalla de acceso
  denegado mediante los manejadores registrados en `app/main.py`.

El recorrido completo de un pedido autenticado es, entonces: cookie de sesión, router, guarda
de rol, servicio de dominio, ORM y respuesta. El flujo es trazable y predecible, que es la
propiedad que el whitepaper buscaba con la combinación de capas y filtros.

### 2.3. Publish-Subscribe (sistema distribuido)

El whitepaper modela la comunicación entre la coordinación y los estudiantes con
Publish-Subscribe: cada actividad es un *topic* y la inscripción del estudiante lo deja
suscripto. La intención es que quien publica un cambio no necesite conocer a los suscriptos.

En el código, la suscripción es la fila de `Inscripcion` (un estudiante inscripto en una
actividad), y la publicación de un cambio ocurre cuando la coordinación edita una actividad ya
publicada: en `app/routers/admin_actividades.py`, la función `actualizar` recorre los inscriptos
de la actividad (`enrollment_svc.inscriptos`) y notifica a cada uno con `notify(...)`. El
servicio de notificación está en `app/notifications.py`: `notify` escribe una fila en la tabla
`notifications` y, si corresponde, envía un correo.

**Diferencia con el diseño declarado.** El whitepaper preveía un broker Redis como
intermediario. El MVP conserva la semántica del estilo (el publicador escribe el evento y el
sistema lo entrega a los suscriptos, sin que el publicador los conozca de forma individual)
pero reemplaza el broker externo por una entrega en proceso: la notificación se persiste en la
base interna y se envía por correo de manera sincrónica. El punto de extensión queda aislado en
`notify`, de modo que incorporar un broker real no afecta al resto del código. De los tres
eventos descritos en el whitepaper, el MVP implementa la entrega para `actividad.modificada`
(aviso a los inscriptos al editar); el broadcast diferido de `actividad.creada` y el aviso de
baja de una actividad quedan fuera del alcance de esta versión.

### 2.4. Single Event Processing (sistema basado en eventos)

El whitepaper describe la inscripción como una concatenación de eventos singulares, donde la
salida de un paso es la entrada del siguiente. La tabla siguiente mapea cada paso declarado con
el lugar del código que lo resuelve.

| Paso declarado | Dónde se resuelve en el código |
|---|---|
| 1. Clic en "Inscribirme" | `POST /actividades/{id}/inscribir`, función `inscribir` en `app/routers/enrollment.py` |
| 2. Verificación de sesión | Guarda `require_roles("estudiante")` en `app/security.py` |
| 3. Control de cupo | `inscribir` en `app/services/enrollment.py`, con bloqueo de fila y comparación contra `cupo_max` |
| 4. Control de inscripción duplicada | `inscribir`: comprueba si ya existe una inscripción activa del estudiante |
| 5. Registro de la inscripción | `inscribir`: inserta o reactiva la fila `Inscripcion` |
| 6. Descuento del cupo | Se deriva en lectura: `cupo_info` en `app/services/actividades.py` calcula los lugares libres |
| 7. Actualización del inicio del alumno | `home` en `app/routers/enrollment.py` consulta las inscripciones vigentes en vivo |
| 8. Mail de confirmación | `notify(..., email_subject=...)` en `app/notifications.py`, que usa `send_email` |
| 9. Recordatorio agendado | La fila `Inscripcion` nace con `reminded = False` (`app/models.py`); el job lo toma luego |
| 10. Mail de recordatorio 24 horas antes | `send_reminders` en `app/scheduler.py`, ejecutado periódicamente por APScheduler |
| 11. Actualización del panel de la coordinación | `panel` en `app/routers/admin_actividades.py` lee el resumen en vivo |

Cada paso es discreto y se procesa de forma aislada, sin un flujo continuo de eventos ni
correlación entre varios eventos, que es lo que distingue a Single Event Processing de los
patrones de stream o de eventos complejos. La diferencia con el diseño declarado está en el
paso 9: el recordatorio no se agenda de forma individual al inscribirse, sino que un proceso
horario detecta las inscripciones cuyas actividades comienzan en las próximas veinticuatro
horas y todavía no fueron avisadas.

---

## 3. Patrones de diseño de implementación

Además de los estilos arquitectónicos, el código aplica varios patrones de diseño concretos que
sostienen los atributos de calidad declarados en el whitepaper (seguridad, fiabilidad,
auditabilidad, interoperabilidad).

| Patrón | Dónde está | Qué resuelve |
|---|---|---|
| Inyección de dependencias | `Depends(get_db)`, `Depends(require_roles(...))` en `app/routers/` | Desacopla cada endpoint de la obtención de la sesión de base de datos y del usuario actual |
| Capa de servicios sobre el ORM | `app/services/*.py` | Aísla la lógica de dominio del acceso a datos; los routers no construyen consultas |
| Guarda de acceso por rol | `require_roles` y `current_user_required` en `app/security.py` | Centraliza el control de acceso (seguridad) en un único lugar reutilizable |
| Bloqueo pesimista | `select(...).with_for_update()` en `inscribir`, `app/services/enrollment.py` | Garantiza que dos inscripciones simultáneas no superen el cupo (fiabilidad) |
| Estrategia de envío de correo | `send_email` en `app/email_util.py` | Elige en tiempo de ejecución entre un servidor SMTP real y una salida de consola |
| Punto de adaptación al SIU | `legajo_is_valid` en `app/services/identity.py` | Aísla la verificación de matrícula para poder reemplazar el simulador por el SIU real (interoperabilidad) |
| Registro auditable | Filas de `Asistencia` con `validated_by` y `validated_at` en `app/models.py` | Deja trazabilidad de cada acreditación (auditabilidad) |
| Token rotativo | `open_or_rotate` y `check_in` en `app/services/asistencia.py` | Renueva el código de asistencia por tiempo y valida la acreditación |

---

## 4. Diferencias del MVP respecto del diseño declarado

Las siguientes decisiones reducen la superficie del sistema para lograr un despliegue único y
confiable, sin alterar la intención de los estilos declarados. Cada una mantiene un punto de
extensión limpio para volver al diseño original.

- El broker Redis del estilo Publish-Subscribe se reemplaza por la notificación en proceso del
  servicio `notify` (tabla interna y correo).
- Los dashboards previstos con Dash se resuelven con gráficos Chart.js renderizados en el
  servidor (`app/templates/analytics/dashboard.html`).
- La verificación contra el SIU Guaraní se simula con la tabla `valid_legajos`, detrás de
  `app/services/identity.py`.
- El esquema se crea al iniciar con `Base.metadata.create_all` en lugar de migraciones
  administradas.
