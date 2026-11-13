from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.security import get_current_admin, hash_password
from database.db import execute_mutation, execute_query, get_db_mode

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
            u.perfil_id,
            p.name AS perfil_name,
            p.description AS perfil_description,
            u.created_at
        FROM usuario u
        LEFT JOIN perfil p ON u.perfil_id = p.id
        ORDER BY u.id ASC
    """
    rows = execute_query(query)
    for r in rows:
        r["is_admin"] = bool(r.get("is_admin"))
    return rows


@router.get(
    "/profiles",
    summary="Listar Perfis Disponíveis (SELECT p.name FROM perfil)",
    description="Retorna os nomes e dados dos perfis cadastrados executando `SELECT p.name FROM perfil`.",
)
def list_profiles(admin: dict[str, Any] = Depends(get_current_admin)) -> list[dict[str, Any]]:
    query = "SELECT p.id, p.name, p.description, p.created_at FROM perfil p ORDER BY p.id ASC"
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
    mode = get_db_mode()
    ph = "%s" if mode == "postgres" else "?"

    # Check if user exists
    user_rows = execute_query(f"SELECT id, username FROM usuario WHERE id = {ph}", (user_id,))
    if not user_rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    user = user_rows[0]

    # Resolve target perfil_id
    target_perfil_id = payload.perfil_id
    if target_perfil_id is None and payload.perfil_name:
        p_rows = execute_query(f"SELECT id FROM perfil WHERE name = {ph}", (payload.perfil_name,))
        if not p_rows:
            raise HTTPException(status_code=400, detail=f"Perfil '{payload.perfil_name}' não existe.")
        target_perfil_id = p_rows[0]["id"]

    if target_perfil_id is not None:
        p_check = execute_query(f"SELECT id, name FROM perfil WHERE id = {ph}", (target_perfil_id,))
        if not p_check:
            raise HTTPException(status_code=400, detail=f"Perfil de ID {target_perfil_id} não existe.")
        perfil_name = p_check[0]["name"]
    else:
        perfil_name = None

    # Update perfil_id of user
    update_sql = f"UPDATE usuario SET perfil_id = {ph} WHERE id = {ph}"
    execute_mutation(update_sql, (target_perfil_id, user_id))

    return {
        "message": f"Perfil do usuário '{user['username']}' atualizado com sucesso para '{perfil_name}'.",
        "user_id": user_id,
        "username": user["username"],
        "perfil_id": target_perfil_id,
        "perfil_name": perfil_name,
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
    mode = get_db_mode()
    ph = "%s" if mode == "postgres" else "?"

    existing = execute_query(f"SELECT id FROM usuario WHERE username = {ph}", (payload.username,))
    if existing:
        raise HTTPException(status_code=400, detail=f"Nome de usuário '{payload.username}' já está em uso.")

    # Validate perfil if provided
    if payload.perfil_id is not None:
        p_check = execute_query(f"SELECT id FROM perfil WHERE id = {ph}", (payload.perfil_id,))
        if not p_check:
            raise HTTPException(status_code=400, detail="Perfil especificado não existe.")

    pwd_hash = hash_password(payload.password)
    admin_val = (True if payload.is_admin else False) if mode == "postgres" else (1 if payload.is_admin else 0)

    insert_sql = f"INSERT INTO usuario (username, password_hash, is_admin, perfil_id) VALUES ({ph}, {ph}, {ph}, {ph})"
    execute_mutation(insert_sql, (payload.username, pwd_hash, admin_val, payload.perfil_id))

    created = execute_query(
        f"""
        SELECT u.id, u.username, u.is_admin, u.perfil_id, p.name AS perfil_name
        FROM usuario u
        LEFT JOIN perfil p ON u.perfil_id = p.id
        WHERE u.username = {ph}
        """,
        (payload.username,),
    )
    return {
        "message": "Usuário criado pelo administrador com sucesso!",
        "user": created[0] if created else {},
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
    mode = get_db_mode()
    ph = "%s" if mode == "postgres" else "?"

    user_rows = execute_query(f"SELECT id, username, is_admin FROM usuario WHERE id = {ph}", (user_id,))
    if not user_rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    updates = []
    params = []

    if payload.username is not None:
        # Check uniqueness
        check_u = execute_query(f"SELECT id FROM usuario WHERE username = {ph} AND id != {ph}", (payload.username, user_id))
        if check_u:
            raise HTTPException(status_code=400, detail="Nome de usuário já utilizado.")
        updates.append(f"username = {ph}")
        params.append(payload.username)

    if payload.password is not None and payload.password.strip():
        updates.append(f"password_hash = {ph}")
        params.append(hash_password(payload.password))

    if payload.is_admin is not None:
        admin_val = (True if payload.is_admin else False) if mode == "postgres" else (1 if payload.is_admin else 0)
        updates.append(f"is_admin = {ph}")
        params.append(admin_val)

    if payload.perfil_id is not None:
        p_check = execute_query(f"SELECT id FROM perfil WHERE id = {ph}", (payload.perfil_id,))
        if not p_check:
            raise HTTPException(status_code=400, detail="Perfil não encontrado.")
        updates.append(f"perfil_id = {ph}")
        params.append(payload.perfil_id)

    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização.")

    params.append(user_id)
    sql = f"UPDATE usuario SET {', '.join(updates)} WHERE id = {ph}"
    execute_mutation(sql, tuple(params))

    updated = execute_query(
        f"""
        SELECT u.id, u.username, u.is_admin, u.perfil_id, p.name AS perfil_name
        FROM usuario u
        LEFT JOIN perfil p ON u.perfil_id = p.id
        WHERE u.id = {ph}
        """,
        (user_id,),
    )
    return {
        "message": "Usuário atualizado com sucesso!",
        "user": updated[0] if updated else {},
    }


@router.delete(
    "/users/{user_id}",
    summary="Excluir Usuário",
)
def delete_user(
    user_id: int,
    admin: dict[str, Any] = Depends(get_current_admin),
) -> dict[str, Any]:
    mode = get_db_mode()
    ph = "%s" if mode == "postgres" else "?"

    # Check if target is current admin
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta de administrador.")

    user_rows = execute_query(f"SELECT id, username FROM usuario WHERE id = {ph}", (user_id,))
    if not user_rows:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    execute_mutation(f"DELETE FROM usuario WHERE id = {ph}", (user_id,))
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
    mode = get_db_mode()
    ph = "%s" if mode == "postgres" else "?"

    existing = execute_query(f"SELECT id FROM perfil WHERE name = {ph}", (payload.name,))
    if existing:
        raise HTTPException(status_code=400, detail=f"Perfil '{payload.name}' já existe.")

    execute_mutation(
        f"INSERT INTO perfil (name, description) VALUES ({ph}, {ph})",
        (payload.name, payload.description or ""),
    )
    created = execute_query(f"SELECT id, name, description FROM perfil WHERE name = {ph}", (payload.name,))
    return {
        "message": "Perfil criado com sucesso!",
        "profile": created[0] if created else {},
    }
