from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from publisher.database.connection import get_connection
from publisher.profiles.profiles import PROFILES


router = APIRouter(
    prefix="/first-example",
    tags=["FirstExample"],
)


class QueryRequest(BaseModel):
    sql: str = Field(
        ...,
        min_length=1,
        description="SQL statement to execute against the database.",
        examples=[
            "SELECT name, city FROM people",
            "WITH recent AS (SELECT 1 AS value) SELECT value FROM recent",
        ],
    )


def validate_read_only_sql(sql: str) -> None:
    normalized_sql = sql.lstrip().upper()
    if not (normalized_sql.startswith("SELECT") or normalized_sql.startswith("WITH")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only read-only SQL statements starting with SELECT or WITH are allowed.",
        )


def execute_sql_query(sql: str) -> list[dict]:
    """Execute a SQL statement and return the result as a list of dictionaries."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)

            if cursor.description is None:
                return []

            columns = [column.name for column in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row, strict=False)) for row in rows]


@router.post(
    "/query",
    summary="Execute a read-only SQL query using a profile header",
    description=(
        "Send the SQL statement in the JSON body and the profile name in the "
        "`X-Profile-Name` header. The response is transformed according to the "
        "selected profile. Only read-only SQL statements are accepted."
    ),
    response_description="Rows returned by the database after profile transformation.",
)
def get_query_result(
    payload: QueryRequest,
    x_profile_name: str = Header(
        ...,
        alias="X-Profile-Name",
        description="Profile name used to transform string values in the result.",
        examples={
            "profile_a": {
                "summary": "Uppercase profile",
                "value": "A",
            },
            "profile_b": {
                "summary": "Lowercase profile",
                "value": "B",
            },
        },
    ),
) -> list[dict]:
    validate_read_only_sql(payload.sql)

    profile = PROFILES.get(x_profile_name)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown profile: {x_profile_name}",
        )

    results = execute_sql_query(payload.sql)
    return profile.apply(results)