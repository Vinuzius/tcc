from sqlalchemy import create_engine, text

from database.connection import get_connection

from publisher.database.connection import get_connection


class DatabaseService:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        with self.engine.connect() as connection:
            result = connection.execute(
                text(sql),
                params or {},
            )

            return result.mappings().all()



def main() -> None:
    database = DatabaseService(DATABASE_URL)

    employees = database.query(
        """
        select education, age
        from employees e
        where joiningyear > :year;
        """,
        {"year": 2016},
    )

    for employee in employees:
        print(employee["education"], employee["age"])

    with get_connection() as connection:

        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            result = cursor.fetchone()

            print(result[0])


if __name__ == "__main__":
    main()