import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.privacy_engine import PrivacyEngine
from app.security import get_current_user
from database.connections import arani_query, source_query

router = APIRouter(prefix="/api/query", tags=["Consultas SQL"])

# Regras vêm do Arani; os dados vêm da fonte (somente leitura).
engine = PrivacyEngine(arani_query=arani_query, source_query=source_query)


class QueryRequest(BaseModel):
    sql: str = Field(
        ...,
        min_length=1,
        description="Instrução SQL read-only a ser executada na fonte de dados.",
        examples=["SELECT * FROM employee LIMIT 5"],
    )


class QueryResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool = False
    execution_time_ms: float
    user_profile: str | None = None
    username: str | None = None


@router.post(
    "",
    response_model=QueryResponse,
    summary="Executar Consulta SQL Read-Only",
    description=(
        "Executa uma consulta SELECT/WITH na fonte de dados e aplica ao resultado "
        "as regras de privacidade do perfil do usuário autenticado."
    ),
)
def run_sql_query(
    request: QueryRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> QueryResponse:
    start_time = time.perf_counter()

    try:
        # current_user precisa trazer "id" e "profile_id" (ver security.get_current_user)
        result = engine.execute(current_user, request.sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Erro na execução da consulta SQL: {exc}",
        )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    return QueryResponse(
        sql=request.sql.strip(),
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        truncated=result["truncated"],
        execution_time_ms=elapsed_ms,
        user_profile=current_user.get("profile_name"),
        username=current_user.get("username"),
    )
