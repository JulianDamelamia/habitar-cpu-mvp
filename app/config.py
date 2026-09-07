"""Application settings loaded from environment / .env."""
import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

# Session cookies are signed with SECRET_KEY. Never sign with a weak/guessable value:
# anyone who knows the key can forge a session and impersonate any rol. We reject not
# just exact placeholders but any low-entropy or placeholder-style key (too short, or
# containing words like "change"/"secret"/"example"). A near-miss like
# "dev-secret-change-me-7f3a..." must NOT pass. When rejected, fall back to a random
# ephemeral key (secure, but sessions reset on restart / differ per worker) and warn.
_WEAK_MARKERS = ("change", "secret", "placeholder", "example")


def _is_weak_secret(raw: str) -> bool:
    if len(raw) < 32:
        return True
    low = raw.lower()
    return any(marker in low for marker in _WEAK_MARKERS)


def _resolve_secret_key() -> str:
    raw = os.getenv("SECRET_KEY", "").strip()
    if _is_weak_secret(raw):
        logging.getLogger("habitar.config").warning(
            "SECRET_KEY is unset, too short, or a placeholder-style value; using a random "
            "ephemeral key. Set a strong SECRET_KEY (e.g. `python -c \"import secrets; "
            "print(secrets.token_urlsafe(32))\"`) for stable, multi-worker sessions."
        )
        return secrets.token_urlsafe(32)
    return raw


def _normalize_db_url(url: str) -> str:
    """Ensure SQLAlchemy uses the psycopg (v3) driver."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Módulo Habitar")
    DATABASE_URL: str = _normalize_db_url(os.getenv("DATABASE_URL", ""))
    SECRET_KEY: str = _resolve_secret_key()
    SESSION_HTTPS_ONLY: bool = os.getenv("SESSION_HTTPS_ONLY", "").lower() in ("1", "true", "yes")
    REQUIRED_CREDITS: int = int(os.getenv("REQUIRED_CREDITS", "10"))

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "Modulo Habitar <no-reply@example.com>")


settings = Settings()
