import pytest
from database.connections import get_arani_connection, get_source_connection


def _postgres_available() -> bool:
    try:
        with get_arani_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL server is not running")
def test_postgres_connections():
    with get_arani_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            assert cursor.fetchone() == (1,)

    with get_source_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            assert cursor.fetchone() == (1,)
