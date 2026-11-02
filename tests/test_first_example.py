from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg import OperationalError

from main import app


client = TestClient(app)


def test_query_returns_service_unavailable_when_database_connection_fails() -> None:
    with patch(
        "app.routers.first_example.execute_read_query",
        side_effect=OperationalError("database unavailable"),
    ):
        response = client.post(
            "/first-example/query",
            json={"sql": "SELECT 1"},
        )

    assert response.status_code == 503
    assert "PostgreSQL database is unavailable" in response.json()["detail"]
