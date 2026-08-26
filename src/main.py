from publisher.database.connection import get_connection
from publisher.profiles.profiles import PROFILE_A


def main() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT education, city
                FROM employees
                WHERE joiningyear >= %s
                  AND everbenched = %s
                  AND gender = %s;
                """,
                (2018, "Yes", "Female"),
            )

            results = cursor.fetchall()

            # Convert psycopg rows to dictionaries
            results = [
                {
                    "education": employee[0],
                    "city": employee[1],
                }
                for employee in results
            ]

            results = PROFILE_A.apply(results)

            for employee in results:
                print(
                    f"Education: {employee['education']}, "
                    f"City: {employee['city']}"
                )


if __name__ == "__main__":
    main()