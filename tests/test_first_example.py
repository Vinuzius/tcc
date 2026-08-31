from fastapi.testclient import TestClient

from main import app


class FakeCursor:
    description = [type("Column", (), {"name": "name"})(), type("Column", (), {"name": "city"})()]

    def __init__(self):
        self.sql = None

    def execute(self, sql: str) -> None:
        self.sql = sql

    def fetchall(self) -> list[tuple[str, str]]:
        return [("Alice", "London")]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_first_example_query_uses_profile_transform(monkeypatch):
    monkeypatch.setattr("app.routers.first_example.get_connection", lambda: FakeConnection())

    client = TestClient(app)
    response = client.post(
        "/first-example/query",
        headers={"X-Profile-Name": "A"},
        json={"sql": "SELECT name, city FROM people"},
    )

    assert response.status_code == 200
    assert response.json() == [{"name": "ALICE", "city": "LONDON"}]


def test_first_example_query_rejects_unknown_profile():
    client = TestClient(app)
    response = client.post(
        "/first-example/query",
        headers={"X-Profile-Name": "missing"},
        json={"sql": "SELECT 1"},
    )

    assert response.status_code == 400