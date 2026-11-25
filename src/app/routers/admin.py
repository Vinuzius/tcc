from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.security import get_current_admin, hash_password
from database.db import execute_mutation, execute_query

router = APIRouter(prefix="/api/admin", tags=["Administração de Usuários e Perfis"])


class UpdateProfileRequest(BaseModel):
    perfil_id: int | None = Field(default=None, description="ID do novo perfil")
    perfil_name: str | None = Field(default=None, description="Nome do novo perfil (ex: de SELECT p.name FROM perfil)")


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    is_admin: bool = Field(default=False)
    perfil_id: int | None = Field(default=None, description="ID do perfil atribuído pelo admin")


class UpdateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    password: str | None = Field(default=None, min_length=4, max_length=100)
    is_admin: bool | None = Field(default=None)
    perfil_id: int | None = Field(default=None)


class CreateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default="")


@router.get(
    "/users",
    summary="Listar Todos os Usuários Cadastrados",
    description="Retorna a lista completa de usuários cadastrados com seus respectivos perfis.",
)
def list_users(admin: dict[str, Any] = Depends(get_current_admin)) -> list[dict[str, Any]]:
    query = """
        SELECT 
            u.id, 
            u.username, 
            u.is_admin, 
            u.profile_id,
            p.name AS profile_name,
            p.description AS profile_description,
            u.created_at
        FROM app_user u
        LEFT JOIN profile p ON u.profile_id = p.id
        ORDER BY u.id ASC
    """
    rows = execute_query(query)
    return [
        {
            "id": r["id"],
            "username": r["username"],
            "is_admin": bool(r.get("is_admin")),
            "profile_id": r["profile_id"],
            "perfil_id": r["profile_id"],
            "profile_name": r["profile_name"],
            "perfil_name": r["profile_name"],
            "profile_description": r["profile_description"],
            "perfil_description": r["profile_description"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.get(
    "/profiles",
    summary="Listar Perfis Disponíveis (SELECT p.name FROM profile)",
    description="Retorna os nomes e dados dos perfis cadastrados executando `SELECT p.name FROM profile`.",
)
def list_profiles(admin: dict[str, Any] = Depends(get_current_admin)) -> list[dict[str, Any]]:
    query = "SELECT p.id, p.name, p.description, p.created_at FROM profile p ORDER BY p.id ASC"
    return execute_query(query)


@router.patch(
    "/users/{user_id}/profile",
    summary="Modificar o Perfil de um Usuário",
    description="Permite que o administrador altere o perfil de um usuário selecionando a partir dos perfis disponíveis.",
)
def update_user_profile(
    user_id: int,
    payload: UpdateProfileRequest,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    # Check if user exists
    user_rows = execute_query("SELECT id, username FROM app_user WHERE id = %s", (user_id,))
    if not user_rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    user = user_rows[0]

    # Resolve target profile_id
    target_profile_id = payload.perfil_id
    if target_profile_id is None and payload.perfil_name:
        p_rows = execute_query("SELECT id FROM profile WHERE name = %s", (payload.perfil_name,))
        if not p_rows:
            raise HTTPException(status_code=400, detail=f"Perfil '{payload.perfil_name}' não existe.")
        target_profile_id = p_rows[0]["id"]

    if target_profile_id is not None:
        p_check = execute_query("SELECT id, name FROM profile WHERE id = %s", (target_profile_id,))
        if not p_check:
            raise HTTPException(status_code=400, detail=f"Perfil de ID {target_profile_id} não existe.")
        profile_name = p_check[0]["name"]
    else:
        profile_name = None

    # Update profile_id of user along with audit columns
    update_sql = """
        UPDATE app_user
        SET profile_id = %s, profile_assigned_by_id = %s, profile_assigned_at = now()
        WHERE id = %s
    """
    execute_mutation(update_sql, (target_profile_id, admin["id"], user_id))

    return {
        "message": f"Perfil do usuário '{user['username']}' atualizado com sucesso para '{profile_name}'.",
        "user_id": user_id,
        "username": user["username"],
        "perfil_id": target_profile_id,
        "perfil_name": profile_name,
    }


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar Usuário Manualmente (com perfil escolhido pelo Admin)",
)
def create_user_by_admin(
    payload: CreateUserRequest,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    existing = execute_query("SELECT id FROM app_user WHERE username = %s", (payload.username,))
    if existing:
        raise HTTPException(status_code=400, detail=f"Nome de usuário '{payload.username}' já está em uso.")

    # Validate profile if provided
    if payload.perfil_id is not None:
        p_check = execute_query("SELECT id FROM profile WHERE id = %s", (payload.perfil_id,))
        if not p_check:
            raise HTTPException(status_code=400, detail="Perfil especificado não existe.")

    pwd_hash = hash_password(payload.password)

    if payload.perfil_id is not None:
        insert_sql = """
            INSERT INTO app_user (username, password_hash, is_admin, profile_id, profile_assigned_by_id, profile_assigned_at)
            VALUES (%s, %s, %s, %s, %s, now())
        """
        execute_mutation(insert_sql, (payload.username, pwd_hash, bool(payload.is_admin), payload.perfil_id, admin["id"]))
    else:
        insert_sql = "INSERT INTO app_user (username, password_hash, is_admin, profile_id) VALUES (%s, %s, %s, %s)"
        execute_mutation(insert_sql, (payload.username, pwd_hash, bool(payload.is_admin), None))

    created = execute_query(
        """
        SELECT u.id, u.username, u.is_admin, u.profile_id, p.name AS profile_name
        FROM app_user u
        LEFT JOIN profile p ON u.profile_id = p.id
        WHERE u.username = %s
        """,
        (payload.username,),
    )
    user_resp = {}
    if created:
        c = created[0]
        user_resp = {
            "id": c["id"],
            "username": c["username"],
            "is_admin": bool(c.get("is_admin")),
            "profile_id": c["profile_id"],
            "perfil_id": c["profile_id"],
            "profile_name": c["profile_name"],
            "perfil_name": c["profile_name"],
        }
    return {
        "message": "Usuário criado pelo administrador com sucesso!",
        "user": user_resp,
    }


@router.put(
    "/users/{user_id}",
    summary="Atualizar Dados Completos do Usuário",
)
def update_user_by_admin(
    user_id: int,
    payload: UpdateUserRequest,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    user_rows = execute_query("SELECT id, username, is_admin FROM app_user WHERE id = %s", (user_id,))
    if not user_rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    updates = []
    params: list[Any] = []

    if payload.username is not None:
        check_u = execute_query("SELECT id FROM app_user WHERE username = %s AND id != %s", (payload.username, user_id))
        if check_u:
            raise HTTPException(status_code=400, detail="Nome de usuário já utilizado.")
        updates.append("username = %s")
        params.append(payload.username)

    if payload.password is not None and payload.password.strip():
        updates.append("password_hash = %s")
        params.append(hash_password(payload.password))

    if payload.is_admin is not None:
        updates.append("is_admin = %s")
        params.append(bool(payload.is_admin))

    if payload.perfil_id is not None:
        p_check = execute_query("SELECT id FROM profile WHERE id = %s", (payload.perfil_id,))
        if not p_check:
            raise HTTPException(status_code=400, detail="Perfil não encontrado.")
        updates.append("profile_id = %s")
        params.append(payload.perfil_id)
        updates.append("profile_assigned_by_id = %s")
        params.append(admin["id"])
        updates.append("profile_assigned_at = now()")

    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização.")

    params.append(user_id)
    sql = f"UPDATE app_user SET {', '.join(updates)} WHERE id = %s"
    execute_mutation(sql, tuple(params))

    updated = execute_query(
        """
        SELECT u.id, u.username, u.is_admin, u.profile_id, p.name AS profile_name
        FROM app_user u
        LEFT JOIN profile p ON u.profile_id = p.id
        WHERE u.id = %s
        """,
        (user_id,),
    )
    user_resp = {}
    if updated:
        u = updated[0]
        user_resp = {
            "id": u["id"],
            "username": u["username"],
            "is_admin": bool(u.get("is_admin")),
            "profile_id": u["profile_id"],
            "perfil_id": u["profile_id"],
            "profile_name": u["profile_name"],
            "perfil_name": u["profile_name"],
        }
    return {
        "message": "Usuário atualizado com sucesso!",
        "user": user_resp,
    }


@router.delete(
    "/users/{user_id}",
    summary="Excluir Usuário",
)
def delete_user(
    user_id: int,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta de administrador.")

    user_rows = execute_query("SELECT id, username FROM app_user WHERE id = %s", (user_id,))
    if not user_rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    execute_mutation("DELETE FROM app_user WHERE id = %s", (user_id,))
    return {"message": f"Usuário '{user_rows[0]['username']}' excluído com sucesso."}


@router.post(
    "/profiles",
    status_code=status.HTTP_201_CREATED,
    summary="Criar Novo Perfil",
)
def create_profile(
    payload: CreateProfileRequest,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    existing = execute_query("SELECT id FROM profile WHERE name = %s", (payload.name,))
    if existing:
        raise HTTPException(status_code=400, detail=f"Perfil '{payload.name}' já existe.")

    execute_mutation(
        "INSERT INTO profile (name, description) VALUES (%s, %s)",
        (payload.name, payload.description or ""),
    )
    created = execute_query("SELECT id, name, description FROM profile WHERE name = %s", (payload.name,))
    return {
        "message": "Perfil criado com sucesso!",
        "profile": created[0] if created else {},
    }
