from typing import Any

from database.connections import source_query


def ensure_read_query(sql: str) -> str:
    """Allow only one read-only SQL statement."""
    statement = sql.strip()
    if not statement:
        raise ValueError("A SQL query is required")

    if statement.endswith(";"):
        statement = statement[:-1].rstrip()

    if ";" in statement:
        raise ValueError("Only one SQL statement is allowed")

    first_keyword = statement.split(None, 1)[0].upper()
    if first_keyword not in {"SELECT", "WITH"}:
        raise ValueError("Only SELECT or WITH queries are allowed")

    return statement


def execute_read_query(sql: str) -> list[dict[str, Any]]:
    statement = ensure_read_query(sql)
    return source_query(statement)
