
from datetime import datetime, timedelta, timezone
import re

def parse_date_time(value: str) -> datetime:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", value or ""):
        raise ValueError("La fecha debe tener formato AAAA-MM-DDTHH:MM.")
    # datetime-local -> naive; store as UTC-aware (wall-clock kept for display).
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def parse_duracion(value: str) -> timedelta:
    if not re.fullmatch(r"\d{2}:\d{2}", value.strip()):
        raise ValueError("La duración debe tener formato HH:MM.")
    try:
        hours_text, minutes_text = value.strip().split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except ValueError:
        raise ValueError("La duración debe tener formato HH:MM.") from None
    if hours > 25 or not 0 <= minutes < 60 or hours == 0 and minutes == 0:
        raise ValueError("La duración debe ser mayor que 00:00 y tener minutos válidos.")
    return timedelta(hours=hours, minutes=minutes)


def parse_intervalo_tiempo(
    fecha_inicio: str,
    fecha_fin: str = "",
    duracion: str = "",
    modo_finalizacion: str = "duracion",
) -> tuple[datetime, datetime]:
    """Parse both dates and validate order. Raises ValueError on malformed/invalid input."""
    inicio = parse_date_time(fecha_inicio)
    if modo_finalizacion == "duracion":
        if duracion:
            fin = inicio + parse_duracion(duracion)
        else:
            # Compatibility with clients that still submit an explicit end date.
            fin = parse_date_time(fecha_fin)
    elif modo_finalizacion == "fecha_fin":
        fin = parse_date_time(fecha_fin)
    else:
        raise ValueError("Modo de finalización inválido.")
    hoy = datetime.now(timezone.utc).date()
    if inicio.date() < hoy or fin.date() < hoy:
        raise ValueError("Las fechas no pueden ser anteriores al día de hoy.")
    if fin < inicio:
        raise ValueError("La fecha de fin es anterior al inicio.")
    return inicio, fin


def formatear_duracion(inicio: datetime, fin: datetime) -> str:
    total_minutes = max(0, int((fin - inicio).total_seconds() // 60))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"