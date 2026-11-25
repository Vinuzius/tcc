import csv
import logging
from pathlib import Path

import bcrypt

from database.connections import (
    arani_mutation,
    arani_query,
    run_arani_script,
)

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_DIR = Path(__file__).resolve().parent

execute_query = arani_query
execute_mutation = arani_mutation


def init_database() -> None:
    """Initialize Arani schema/seed, sample public.employee table, and default users."""
    logger.info("Initializing Arani database...")

    # 1. Run Arani schema and seed scripts
    run_arani_script(DB_DIR / "arani_schema.sql")
    run_arani_script(DB_DIR / "arani_seed.sql")

    # 2. Create sample source table public.employee (idempotent) using Arani connection
    execute_mutation(
        """
        CREATE TABLE IF NOT EXISTS public.employee (
            id SERIAL PRIMARY KEY,
            education VARCHAR(50),
            joining_year INTEGER,
            city VARCHAR(100),
            payment_tier INTEGER,
            age INTEGER,
            gender VARCHAR(20),
            ever_benched VARCHAR(10),
            experience_in_current_domain INTEGER,
            leave_or_not INTEGER
        )
        """
    )

    employees = execute_query("SELECT 1 FROM public.employee LIMIT 1")
    csv_path = ROOT_DIR / "docs" / "Example_Table_Employee.csv"
    if not employees and csv_path.exists():
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= 100:
                        break
                    execute_mutation(
                        """
                        INSERT INTO public.employee
                            (education, joining_year, city, payment_tier, age, gender, ever_benched, experience_in_current_domain, leave_or_not)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            row.get("Education"),
                            int(row.get("JoiningYear", 0)),
                            row.get("City"),
                            int(row.get("PaymentTier", 0)),
                            int(row.get("Age", 0)),
                            row.get("Gender"),
                            row.get("EverBenched"),
                            int(row.get("ExperienceInCurrentDomain", 0)),
                            int(row.get("LeaveOrNot", 0)),
                        ),
                    )
        except Exception as exc:
            logger.warning(f"Could not seed public.employee table: {exc}")

    role_exists = execute_query(
        "SELECT 1 FROM pg_roles WHERE rolname = 'source_reader'"
    )
    if role_exists:
        execute_mutation("GRANT SELECT ON public.employee TO source_reader")

    # 3. Seed default users if app_user is empty
    users = execute_query("SELECT id FROM app_user LIMIT 1")
    if not users:
        profiles = execute_query("SELECT id, name FROM profile")
        profile_map = {p["name"]: p["id"] for p in profiles}

        seed_users = [
            ("admin", "admin123", True, profile_map.get("Administrador")),
            ("user_a", "usera123", False, profile_map.get("A")),
            ("user_b", "userb123", False, profile_map.get("B")),
            ("joao", "user123", False, profile_map.get("Padrão")),
        ]

        for username, password, is_admin, profile_id in seed_users:
            pwd_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            try:
                execute_mutation(
                    """
                    INSERT INTO app_user (username, password_hash, is_admin, profile_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (username, pwd_hash, is_admin, profile_id),
                )
            except Exception as exc:
                logger.warning(f"Error seeding user {username}: {exc}")
