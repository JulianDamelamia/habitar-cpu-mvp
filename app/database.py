"""Database engine, session factory and declarative base."""
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    # Neon's pooled endpoint runs PgBouncer in transaction mode; disable
    # psycopg3 auto-prepared statements to avoid "prepared statement exists" errors.
    connect_args={"prepare_threshold": None},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_schema() -> None:
    """Apply small idempotent schema changes not handled by create_all()."""
    inspector = inspect(engine)
    if not inspector.has_table("carreras"):
        return

    columns = {column["name"] for column in inspector.get_columns("carreras")}
    if "creditos_requeridos" not in columns:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE carreras "
                "ADD COLUMN creditos_requeridos INTEGER NOT NULL DEFAULT 10"
            ))
