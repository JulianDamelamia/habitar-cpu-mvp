import unittest

from sqlalchemy import text

from app.database import engine


class DatabaseConnectionTest(unittest.TestCase):
    def test_database_connection(self):
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))

        self.assertEqual(result.scalar_one(), 1)


if __name__ == "__main__":
    unittest.main()