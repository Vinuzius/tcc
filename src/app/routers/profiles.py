from typing import Any
from fastapi import APIRouter
from database.db import execute_query

router = APIRouter(prefix="/api/profiles", tags=["Perfis"])


@router.get(
    "",
    summary="Listar Nomes dos Perfis (SELECT p.name FROM perfil)",
    description="Executa `SELECT p.name FROM perfil` e retorna os perfis para preenchimento de seletores na UI.",
)
def get_profiles() -> list[dict[str, Any]]:
    query = "SELECT p.id, p.name, p.description FROM perfil p ORDER BY p.id ASC"
    return execute_query(query)
