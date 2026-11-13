import time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import get_current_user
from database.queries import ensure_read_query
from database.db import execute_query

router = APIRouter(prefix="/api/query", tags=["Consultas SQL"])


class QueryRequest(BaseModel):
    sql: str = Field(
        ...,
        min_length=1,
        description="Instrução SQL read-only a ser executada no banco de dados.",
        examples=["SELECT p.name FROM perfil p", "SELECT * FROM employee LIMIT 5"],
    )


class QueryResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: float
    user_profile: str | None = None
    username: str | None = None


@router.post(
    "",
    response_model=QueryResponse,
    summary="Executar Consulta SQL Read-Only",
    description=(
        "Executa uma instrução SQL segura (SELECT ou WITH) e retorna as colunas, "
        "linhas retornadas e tempo de execução."
    ),
)
def run_sql_query(
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> QueryResponse:
    start_time = time.perf_counter()

    try:
        validated_sql = ensure_read_query(request.sql)
        rows = execute_query(validated_sql)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        columns = list(rows[0].keys()) if rows else []

        return QueryResponse(
            sql=validated_sql,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
            user_profile=current_user.get("perfil_name"),
            username=current_user.get("username"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Erro na execução da consulta SQL: {str(e)}",
        )
