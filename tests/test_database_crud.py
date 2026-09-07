import unittest
from uuid import uuid4

from sqlalchemy import inspect, select

from app.database import SessionLocal, engine
from app.models.models import User


class DatabaseCrudTest(unittest.TestCase):
    def setUp(self):
        self.created_users_table = not inspect(engine).has_table(User.__tablename__)
        User.__table__.create(bind=engine, checkfirst=True)
        self.session = SessionLocal()
        self.email = f"test-{uuid4().hex}@example.com"
        self.user_id = None

    def tearDown(self):
        self.session.rollback()
        if self.user_id is not None:
            user = self.session.get(User, self.user_id)
            if user is not None:
                self.session.delete(user)
                self.session.commit()
        self.session.close()
        if self.created_users_table:
            User.__table__.drop(bind=engine, checkfirst=True)

    def test_user_crud(self):
        user = User(
            email=self.email,
            pw_hash="test-hash",
            nombre="Usuario",
            apellido="De Prueba",
        )
        self.session.add(user)
        self.session.commit()
        self.user_id = user.id

        created = self.session.get(User, self.user_id)
        self.assertIsNotNone(created)
        self.assertEqual(created.email, self.email)

        created.nombre = "Usuario Actualizado"
        self.session.commit()

        updated = self.session.scalar(select(User).where(User.id == self.user_id))
        self.assertIsNotNone(updated)
        self.assertEqual(updated.nombre, "Usuario Actualizado")

        self.session.delete(updated)
        self.session.commit()
        self.assertIsNone(self.session.get(User, self.user_id))
        self.user_id = None


if __name__ == "__main__":
    unittest.main()