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
