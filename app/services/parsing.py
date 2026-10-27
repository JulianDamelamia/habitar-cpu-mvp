
from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo

ARGENTINA_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def to_local_datetime(value: datetime) -> datetime:
    """Convert a stored UTC datetime to Argentina local time for display."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ARGENTINA_TIMEZONE)


def parse_date_time(value: str) -> datetime:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", value or ""):
        raise ValueError("La fecha debe tener formato AAAA-MM-DDTHH:MM.")
    local_datetime = datetime.fromisoformat(value).replace(
        tzinfo=ARGENTINA_TIMEZONE
    )
    return local_datetime.astimezone(timezone.utc)


def parse_duracion(value: str) -> timedelta:
    value_clean = value.strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", value_clean):
        raise ValueError("La duración debe tener formato H:MM o HH:MM.")
    try:
        hours_text, minutes_text = value_clean.split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except ValueError:
        raise ValueError("La duración debe tener formato H:MM o HH:MM.") from None
    if hours > 25 or not 0 <= minutes < 60 or (hours == 0 and minutes == 0):
        raise ValueError("La duración debe ser mayor que 0:00 y tener minutos válidos.")
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
    hoy = datetime.now(ARGENTINA_TIMEZONE).date()
    if inicio.date() < hoy or fin.date() < hoy:
        raise ValueError("Las fechas no pueden ser anteriores al día de hoy.")
    if fin < inicio:
        raise ValueError("La fecha de fin es anterior al inicio.")
    return inicio, fin


def formatear_duracion(inicio: datetime, fin: datetime) -> str:
    total_minutes = max(0, int((fin - inicio).total_seconds() // 60))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"