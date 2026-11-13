from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from psycopg import OperationalError

from database.queries import execute_read_query


class QueryRequest(BaseModel):
    sql: str


router = APIRouter(prefix="/first-example", tags=["queries"])


@router.post("/query")
def query_database(request: QueryRequest) -> list[dict[str, Any]]:
    try:
        return execute_read_query(request.sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "The PostgreSQL database is unavailable. "
                "Check POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE, "
                "POSTGRES_USER, and POSTGRES_PASSWORD, then restart the API."
            ),
        ) from exc
