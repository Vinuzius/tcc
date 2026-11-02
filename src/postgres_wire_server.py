import os

from pydantic import BaseModel
from postgres_wire import Handler, create_server

from database.queries import ensure_read_query, execute_read_query


class EmployeeQueryResult(BaseModel):
    education: str
    city: str
    payment_tier: int


class EmployeeQueryHandler(Handler):
    """Serve the employee read example through the PostgreSQL wire protocol."""

    port = int(os.getenv("POSTGRES_WIRE_PORT", "5433"))

    def query(self, sql: str) -> list[EmployeeQueryResult]:
        rows = execute_read_query(ensure_read_query(sql))
        return [EmployeeQueryResult.model_validate(row) for row in rows]

    def check_auth(self, user: str, password: str) -> None:
        configured_user = os.getenv("POSTGRES_WIRE_USER")
        configured_password = os.getenv("POSTGRES_WIRE_PASSWORD")
        if configured_user and user != configured_user:
            raise ValueError("Invalid PostgreSQL wire username")
        if configured_password and password != configured_password:
            raise ValueError("Invalid PostgreSQL wire password")


def main() -> None:
    serve = create_server(EmployeeQueryHandler)
    serve()


if __name__ == "__main__":
    main()
