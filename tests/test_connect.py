import pytest
from database.connection import get_connection
from database.db import is_postgres_available


@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL server is not running")
def test_postgres_connection():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()

            assert result == (1,)
