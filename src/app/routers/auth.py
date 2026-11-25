import os
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.security import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database.db import execute_mutation, execute_query

router = APIRouter(prefix="/api/auth", tags=["Autenticação (OAuth 2.0)"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, description="Nome de usuário para login")
    password: str = Field(..., min_length=4, max_length=100, description="Senha de acesso")


class OAuthLoginRequest(BaseModel):
    provider: str = Field(default="google", description="Provedor OAuth (google, github, institucional)")
    oauth_email: str | None = Field(default=None, description="Email ou identificador retornado pelo provedor OAuth")
    code: str | None = Field(default="demo-auth-code-12345", description="Código de autorização OAuth 2.0")


def get_user_by_username(username: str) -> dict[str, Any] | None:
    query = """
        SELECT 
            u.id, 
            u.username, 
            u.password_hash, 
            u.is_admin, 
            u.profile_id,
            p.name AS profile_name,
            p.description AS profile_description
        FROM app_user u
        LEFT JOIN profile p ON u.profile_id = p.id
        WHERE u.username = %s
        LIMIT 1
    """
    users = execute_query(query, (username,))
    if not users:
        return None
    user = users[0]
    return {
        "id": user["id"],
        "username": user["username"],
        "password_hash": user["password_hash"],
        "is_admin": bool(user.get("is_admin")),
        "profile_id": user["profile_id"],
        "profile_name": user["profile_name"],
        "profile_description": user["profile_description"],
    }


def get_default_profile_id() -> int | None:
    """Find default profile id ('Padrão' or the first available non-admin profile)."""
    profiles = execute_query("SELECT id FROM profile WHERE name = 'Padrão' LIMIT 1")
    if profiles:
        return profiles[0]["id"]
    # Fallback to any profile
    profiles = execute_query("SELECT id FROM profile ORDER BY id ASC LIMIT 1")
    return profiles[0]["id"] if profiles else None


@router.post(
    "/token",
    summary="OAuth 2.0 Password Flow — Obter Access Token Bearer",
    description="Endpoint padrão de especificação OAuth 2.0 (RFC 6749) com fluxo Password Grant.",
)
def oauth_token(form_data: OAuth2PasswordRequestForm = Depends()) -> dict[str, Any]:
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({
        "sub": str(user["id"]),
        "username": user["username"],
        "is_admin": user["is_admin"],
        "profile_id": user["profile_id"],
        "profile_name": user["profile_name"],
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
    }


@router.post(
    "/login",
    summary="Login via JSON (OAuth 2.0 Bearer)",
    description="Autentica o usuário com login e senha e retorna o token de acesso Bearer e dados do usuário.",
)
def login_json(payload: LoginRequest) -> dict[str, Any]:
    user = get_user_by_username(payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas. Verifique seu login e senha.",
        )

    token = create_access_token({
        "sub": str(user["id"]),
        "username": user["username"],
        "is_admin": user["is_admin"],
        "profile_id": user["profile_id"],
        "profile_name": user["profile_name"],
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"],
            "perfil": {
                "id": user["profile_id"],
                "name": user["profile_name"],
                "description": user["profile_description"],
            },
        },
    }


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastro de Novo Usuário (Auto-registro)",
    description=(
        "Cadastra um novo usuário no sistema. Por regra de negócio do sistema, "
        "o usuário sempre recebe o perfil padrão ('Padrão') e não pode ser admin. "
        "Apenas o administrador pode alterar o perfil de um usuário posteriormente."
    ),
)
def register(payload: RegisterRequest) -> dict[str, Any]:
    existing = get_user_by_username(payload.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O nome de usuário '{payload.username}' já está em uso.",
        )

    # Enforce profile rule: regular user cannot pick profile or admin
    default_profile_id = get_default_profile_id()
    pwd_hash = hash_password(payload.password)

    insert_sql = """
        INSERT INTO app_user (username, password_hash, is_admin, profile_id)
        VALUES (%s, %s, %s, %s)
    """
    execute_mutation(insert_sql, (payload.username, pwd_hash, False, default_profile_id))

    new_user = get_user_by_username(payload.username)
    if not new_user:
        raise HTTPException(status_code=500, detail="Erro ao criar usuário.")

    token = create_access_token({
        "sub": str(new_user["id"]),
        "username": new_user["username"],
        "is_admin": new_user["is_admin"],
        "profile_id": new_user["profile_id"],
        "profile_name": new_user["profile_name"],
    })

    return {
        "message": "Usuário cadastrado com sucesso!",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user["id"],
            "username": new_user["username"],
            "is_admin": new_user["is_admin"],
            "perfil": {
                "id": new_user["profile_id"],
                "name": new_user["profile_name"],
                "description": new_user["profile_description"],
            },
        },
    }


@router.get(
    "/me",
    summary="Informações do Usuário Autenticado",
    description="Retorna os dados do usuário atual, incluindo perfil e permissão de admin.",
)
def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "is_admin": current_user["is_admin"],
        "perfil": {
            "id": current_user["profile_id"],
            "name": current_user["profile_name"],
            "description": current_user["profile_description"],
        },
    }


@router.get(
    "/oauth/providers",
    summary="Provedores OAuth 2.0 Suportados",
    description="Lista os provedores de autenticação OAuth 2.0 disponíveis.",
)
def get_oauth_providers() -> list[dict[str, str]]:
    return [
        {
            "id": "google",
            "name": "Google OAuth 2.0",
            "auth_url": "/api/auth/oauth/login?provider=google",
            "icon": "google",
            "description": "Autenticação via Google Single Sign-On (OAuth 2.0)",
        },
        {
            "id": "github",
            "name": "GitHub OAuth 2.0",
            "auth_url": "/api/auth/oauth/login?provider=github",
            "icon": "github",
            "description": "Autenticação via GitHub OAuth App",
        },
        {
            "id": "institucional",
            "name": "OAuth Institucional / Acadêmico",
            "auth_url": "/api/auth/oauth/login?provider=institucional",
            "icon": "university",
            "description": "Autenticação federada acadêmica institucional",
        },
    ]


@router.post(
    "/oauth/login",
    summary="Login / Callback OAuth 2.0",
    description="Processa o login com provedor OAuth 2.0 e emite o token Bearer.",
)
def oauth_login(payload: OAuthLoginRequest) -> dict[str, Any]:
    provider = payload.provider.lower()
    base_username = payload.oauth_email.split("@")[0] if payload.oauth_email else f"oauth_{provider}_user"

    # Check if user already exists
    user = get_user_by_username(base_username)
    if not user:
        # Create user via OAuth with default profile
        default_profile_id = get_default_profile_id()
        random_pwd_hash = hash_password(f"oauth_{os.urandom(8).hex()}")
        execute_mutation(
            "INSERT INTO app_user (username, password_hash, is_admin, profile_id) VALUES (%s, %s, %s, %s)",
            (base_username, random_pwd_hash, False, default_profile_id),
        )
        user = get_user_by_username(base_username)

    if not user:
        raise HTTPException(status_code=500, detail="Falha ao autenticar usuário via OAuth 2.0.")

    token = create_access_token({
        "sub": str(user["id"]),
        "username": user["username"],
        "is_admin": user["is_admin"],
        "profile_id": user["profile_id"],
        "profile_name": user["profile_name"],
        "provider": provider,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
        "provider": provider,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"],
            "perfil": {
                "id": user["profile_id"],
                "name": user["profile_name"],
                "description": user["profile_description"],
            },
        },
    }
