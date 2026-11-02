from database.connection import get_connection


def test_postgres_connection():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()

            assert result == (1,)