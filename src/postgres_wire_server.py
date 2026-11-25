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

    def handle_query(self, sql: bytes) -> None:
        rows = self.query(sql)
        if not rows:
            self.send_row_description([])
            self.send_row_data([])
            self.send_command_complete(b"SELECT\x00")
            return

        self._cached_query = (sql, rows)
        try:
            super().handle_query(sql)
        finally:
            del self._cached_query

    def query(self, sql: str | bytes) -> list[EmployeeQueryResult]:
        cached_query = getattr(self, "_cached_query", None)
        if cached_query is not None and cached_query[0] == sql:
            return cached_query[1]

        if isinstance(sql, bytes):
            sql = sql.rstrip(b"\x00").decode("utf-8")
        rows = execute_read_query(ensure_read_query(sql))
        return [EmployeeQueryResult.model_validate(row) for row in rows]

    def check_auth(self, user: str, password: str) -> None:
        configured_user = os.getenv("POSTGRES_WIRE_USER")
        configured_password = os.getenv("POSTGRES_WIRE_PASSWORD")
        if not configured_user or not configured_password:
            raise ValueError("PostgreSQL wire credentials are not configured")
        if user != configured_user:
            raise ValueError("Invalid PostgreSQL wire username")
        if password != configured_password:
            raise ValueError("Invalid PostgreSQL wire password")


def main() -> None:
    serve = create_server(EmployeeQueryHandler)
    serve()


if __name__ == "__main__":
    main()
