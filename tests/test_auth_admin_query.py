import uuid
import pytest
from fastapi.testclient import TestClient
from main import app
from database.db import execute_mutation, init_database

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database_state():
    init_database()
    # Ensure joao has default profile
    execute_mutation(
        "UPDATE app_user SET profile_id = (SELECT id FROM profile WHERE name = 'Padrão' LIMIT 1) WHERE username = 'joao'"
    )
    yield


def test_frontend_root_and_static_assets():
    response = client.get("/")
    assert response.status_code == 200
    assert "TCC • Sistema de Consultas" in response.text
    assert "text/html" in response.headers["content-type"]

    css_resp = client.get("/static/css/styles.css")
    assert css_resp.status_code == 200
    assert "var(--primary)" in css_resp.text

    js_resp = client.get("/static/js/app.js")
    assert js_resp.status_code == 200


def test_login_oauth_token_success():
    response = client.post(
        "/api/auth/token",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_login_oauth_token_invalid_password():
    response = client.post(
        "/api/auth/token",
        data={"username": "admin", "password": "wrong_password"},
    )
    assert response.status_code == 400
    assert "Nome de usuário ou senha incorretos" in response.json()["detail"]


def test_login_json():
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == "admin"
    assert data["user"]["is_admin"] is True
    assert data["user"]["perfil"]["name"] == "Administrador"


def test_register_creates_user_with_default_profile_and_non_admin():
    uname = f"user_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/auth/register",
        json={"username": uname, "password": "senha123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["username"] == uname
    assert data["user"]["is_admin"] is False
    assert data["user"]["perfil"]["name"] == "Padrão"


def test_me_endpoint_requires_auth():
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_endpoint_with_valid_token():
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "joao", "password": "user123"},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "joao"
    assert data["is_admin"] is False
    assert data["perfil"]["name"] == "Padrão"


def test_regular_user_cannot_access_admin():
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "joao", "password": "user123"},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_admin_can_list_users_and_profiles():
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_resp.json()["access_token"]

    users_resp = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert users_resp.status_code == 200
    users = users_resp.json()
    assert len(users) >= 3

    profiles_resp = client.get(
        "/api/admin/profiles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profiles_resp.status_code == 200
    profiles = profiles_resp.json()
    names = [p["name"] for p in profiles]
    assert "Administrador" in names
    assert "Padrão" in names
    assert "A" in names
    assert "B" in names


def test_admin_can_modify_user_profile():
    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    admin_token = admin_login.json()["access_token"]

    # Get joao's user id
    users_resp = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    joao = next(u for u in users_resp.json() if u["username"] == "joao")

    # Update joao's profile to A
    patch_resp = client.patch(
        f"/api/admin/users/{joao['id']}/profile",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"perfil_name": "A"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["perfil_name"] == "A"

    # Verify update persisted
    verify_resp = client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    joao_updated = next(u for u in verify_resp.json() if u["username"] == "joao")
    assert joao_updated["perfil_name"] == "A"


def test_query_runner_endpoint():
    # Admin sees original data
    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    admin_token = admin_login.json()["access_token"]

    admin_resp = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sql": "SELECT * FROM employee LIMIT 3"},
    )
    assert admin_resp.status_code == 200
    admin_res = admin_resp.json()
    assert "education" in admin_res["columns"]
    assert "city" in admin_res["columns"]
    assert admin_res["row_count"] == 3

    # user_a: city in UPPERCASE
    a_login = client.post(
        "/api/auth/login",
        json={"username": "user_a", "password": "usera123"},
    )
    a_token = a_login.json()["access_token"]
    a_resp = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {a_token}"},
        json={"sql": "SELECT * FROM employee LIMIT 3"},
    )
    assert a_resp.status_code == 200
    a_res = a_resp.json()
    assert "education" in a_res["columns"]
    assert all(r["city"] == r["city"].upper() for r in a_res["rows"] if r["city"])

    # user_b: education column hidden
    b_login = client.post(
        "/api/auth/login",
        json={"username": "user_b", "password": "userb123"},
    )
    b_token = b_login.json()["access_token"]
    b_resp = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {b_token}"},
        json={"sql": "SELECT * FROM employee LIMIT 3"},
    )
    assert b_resp.status_code == 200
    b_res = b_resp.json()
    assert "education" not in b_res["columns"]
    assert all("education" not in r for r in b_res["rows"])

    # Source isolation: app_user and arani.app_user fail
    assert client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sql": "SELECT * FROM app_user"},
    ).status_code == 400
    assert client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sql": "SELECT * FROM arani.app_user"},
    ).status_code == 400

    # Read-only enforcement: CTE with DELETE fails
    assert client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sql": "WITH d AS (DELETE FROM employee RETURNING *) SELECT * FROM d"},
    ).status_code == 400

    # Reject non-read query
    invalid_resp = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"sql": "DELETE FROM employee WHERE id = 1"},
    )
    assert invalid_resp.status_code == 400


def test_oauth_simulated_login():
    response = client.post(
        "/api/auth/oauth/login",
        json={"provider": "google", "oauth_email": "aluno@universidade.edu.br"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["perfil"]["name"] == "Padrão"


def _login(username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_catalog_matches_information_schema():
    from database.connections import arani_query

    catalog_cols = [
        r["name"]
        for r in arani_query(
            """
            SELECT dc.name
            FROM arani.data_column dc
            JOIN arani.data_table dt ON dt.id = dc.data_table_id
            WHERE dt.name = 'employee'
            ORDER BY dc.name
            """
        )
    ]
    table_cols = [
        r["column_name"]
        for r in arani_query(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'employee'
            ORDER BY column_name
            """
        )
    ]
    assert catalog_cols == table_cols
    assert len(catalog_cols) == 9


def test_query_lineage_and_fail_closed_acceptance():
    token_a = _login("user_a", "usera123")
    token_b = _login("user_b", "userb123")

    # 1. Alias
    r1 = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"sql": "SELECT city AS c FROM employee LIMIT 3"},
    )
    assert r1.status_code == 200
    assert all(row["c"] == row["c"].upper() for row in r1.json()["rows"] if row["c"])

    # 2. Expressão
    r2 = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"sql": "SELECT city || '-' || age AS x FROM employee LIMIT 3"},
    )
    assert r2.status_code == 200
    assert all(row["x"] == row["x"].upper() for row in r2.json()["rows"] if row["x"])

    # 3. Subconsulta
    r3 = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"sql": "SELECT t.c FROM (SELECT city AS c FROM employee) t LIMIT 3"},
    )
    assert r3.status_code == 200
    assert all(row["c"] == row["c"].upper() for row in r3.json()["rows"] if row["c"])

    # 4. Self-join com aliases
    r4 = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"sql": "SELECT a.city, b.age FROM employee a JOIN employee b ON a.age = b.age LIMIT 3"},
    )
    assert r4.status_code == 200
    assert all(row["city"] == row["city"].upper() for row in r4.json()["rows"] if row["city"])

    # 5. user_b: alias ocultado + 403 quando nenhuma coluna resta
    r5 = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"sql": "SELECT education AS e, age FROM employee LIMIT 3"},
    )
    assert r5.status_code == 200
    assert "e" not in r5.json()["columns"]
    assert all("e" not in row for row in r5.json()["rows"])

    r5_403 = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"sql": "SELECT education FROM employee"},
    )
    assert r5_403.status_code == 403

    # 6. Tabelas fora do catálogo, UNION e SELECT version() -> 400
    for bad_sql in [
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT city FROM employee UNION SELECT city FROM employee",
        "SELECT version()",
    ]:
        bad = client.post(
            "/api/query",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"sql": bad_sql},
        )
        assert bad.status_code == 400


def test_mandatory_coverage_and_revalidation():
    from database.connections import arani_mutation

    token_a = _login("user_a", "usera123")
    try:
        arani_mutation(
            """
            INSERT INTO arani.profile_attribute_classification
                (profile_id, attribute_set_id, privacy_classification, justification)
            SELECT p.id, s.id, 'QUASI_IDENTIFIER', 'Teste de cobertura obrigatória'
            FROM arani.profile p, arani.attribute_set s
            WHERE p.name = 'A' AND s.name = 'employee_city'
            ON CONFLICT (profile_id, attribute_set_id) DO UPDATE
            SET privacy_classification = 'QUASI_IDENTIFIER'
            """
        )
        resp_hidden = client.post(
            "/api/query",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"sql": "SELECT city, age FROM employee LIMIT 3"},
        )
        assert resp_hidden.status_code == 200
        assert "city" not in resp_hidden.json()["columns"]
    finally:
        arani_mutation(
            """
            DELETE FROM arani.profile_attribute_classification pac
            USING arani.profile p, arani.attribute_set s
            WHERE pac.profile_id = p.id
              AND pac.attribute_set_id = s.id
              AND p.name = 'A'
              AND s.name = 'employee_city'
            """
        )

    resp_restored = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"sql": "SELECT city, age FROM employee LIMIT 3"},
    )
    assert resp_restored.status_code == 200
    assert "city" in resp_restored.json()["columns"]
    assert all(r["city"] == r["city"].upper() for r in resp_restored.json()["rows"] if r["city"])


def test_query_max_rows_truncation(monkeypatch):
    monkeypatch.setenv("QUERY_MAX_ROWS", "10")
    token_a = _login("user_a", "usera123")
    resp = client.post(
        "/api/query",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"sql": "SELECT * FROM employee"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["row_count"] == 10
    assert data["truncated"] is True
