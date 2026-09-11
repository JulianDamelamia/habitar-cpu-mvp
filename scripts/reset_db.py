# scripts/reset_db.py
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.seed import seed_all
from sqlalchemy import text


def reset_database():
    # Salvaguarda: Evitar ejecución accidental en entorno de producción
    if settings.ENVIRONMENT == "production":
        print("OPERACIÓN CANCELADA: No podés ejecutar este script en PRODUCCIÓN.")
        return

    confirmacion = input(
        "⚠️  ¿Está seguro de que desea borrar la base de datos local y repopularla? [y/N]: "
    )
    if confirmacion.lower() != "y":
        print("Operación cancelada.")
        return

    print("Borrando esquema public...")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        conn.execute(text("CREATE SCHEMA public;"))

    print("Creando tablas...")
    Base.metadata.create_all(bind=engine)

    print("Ejecutando seed...")
    db = SessionLocal()
    try:
        seed_all(db)
        print("✅ Base de datos reiniciada con éxito.")
    finally:
        db.close()


if __name__ == "__main__":
    reset_database()