import csv
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# Load .env from project root
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=True)

SQLITE_DB_PATH = ROOT_DIR / "tcc.db"


def is_postgres_available() -> bool:
    """Check if PostgreSQL configured in .env is reachable."""
    if os.getenv("FORCE_SQLITE", "").lower() in ("1", "true", "yes"):
        return False

    try:
        conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            dbname=os.getenv("POSTGRES_DATABASE", "postgres"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            connect_timeout=1,
        )
        conn.close()
        return True
    except Exception:
        return False


def get_db_mode() -> str:
    """Return 'postgres' if reachable and not forced to sqlite, otherwise 'sqlite'."""
    return "postgres" if is_postgres_available() else "sqlite"


def get_sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_postgres_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DATABASE", "postgres"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        options=f"-c search_path={os.getenv('POSTGRES_SCHEMA', 'public')}",
    )


def execute_query(sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    """Execute a read query and return list of dictionaries."""
    mode = get_db_mode()
    params = params or ()

    if mode == "postgres":
        with get_postgres_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return []
                return list(cur.fetchall())
    else:
        with get_sqlite_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            if cur.description is None:
                return []
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def execute_mutation(sql: str, params: tuple | list | None = None) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return lastrowid or affected rows."""
    mode = get_db_mode()
    params = params or ()

    if mode == "postgres":
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
                return cur.rowcount
    else:
        with get_sqlite_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid or cur.rowcount


def init_database() -> None:
    """Initialize schema (perfil, usuario, employee) and seed default data."""
    import bcrypt

    mode = get_db_mode()
    logger.info(f"Initializing database in mode: {mode}")

    if mode == "postgres":
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS perfil (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS usuario (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(100) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        is_admin BOOLEAN DEFAULT FALSE,
                        perfil_id INTEGER REFERENCES perfil(id) ON DELETE SET NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS employee (
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
                    );
                """)
                conn.commit()
    else:
        with get_sqlite_connection() as conn:
            cur = conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS perfil (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS usuario (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    perfil_id INTEGER REFERENCES perfil(id) ON DELETE SET NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS employee (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    education TEXT,
                    joining_year INTEGER,
                    city TEXT,
                    payment_tier INTEGER,
                    age INTEGER,
                    gender TEXT,
                    ever_benched TEXT,
                    experience_in_current_domain INTEGER,
                    leave_or_not INTEGER
                );
            """)
            conn.commit()

    # Seed default profiles
    default_profiles = [
        ("Administrador", "Acesso irrestrito e gerenciamento de perfis e usuários"),
        ("Padrão", "Perfil padrão para novos usuários cadastrados no sistema"),
        ("Pesquisador", "Perfil acadêmico para análise de dados estatísticos"),
        ("LGPD_Anonimizado", "Perfil restrito com regras de proteção LGPD"),
        ("Perfil_A", "Perfil A para testes e transformações"),
        ("Perfil_B", "Perfil B para testes e transformações"),
    ]

    for name, desc in default_profiles:
        try:
            execute_mutation(
                "INSERT INTO perfil (name, description) VALUES (%s, %s)" if mode == "postgres"
                else "INSERT OR IGNORE INTO perfil (name, description) VALUES (?, ?)",
                (name, desc),
            )
        except Exception:
            pass

    # Seed default users if table is empty
    users = execute_query("SELECT id FROM usuario LIMIT 1")
    if not users:
        admin_profile = execute_query("SELECT id FROM perfil WHERE name = 'Administrador' LIMIT 1")
        admin_profile_id = admin_profile[0]["id"] if admin_profile else None

        default_profile = execute_query("SELECT id FROM perfil WHERE name = 'Padrão' LIMIT 1")
        default_profile_id = default_profile[0]["id"] if default_profile else None

        research_profile = execute_query("SELECT id FROM perfil WHERE name = 'Pesquisador' LIMIT 1")
        research_profile_id = research_profile[0]["id"] if research_profile else None

        # Hashes
        admin_pwd_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        user_pwd_hash = bcrypt.hashpw(b"user123", bcrypt.gensalt()).decode()
        maria_pwd_hash = bcrypt.hashpw(b"maria123", bcrypt.gensalt()).decode()

        seed_users = [
            ("admin", admin_pwd_hash, True if mode == "postgres" else 1, admin_profile_id),
            ("joao", user_pwd_hash, False if mode == "postgres" else 0, default_profile_id),
            ("maria", maria_pwd_hash, False if mode == "postgres" else 0, research_profile_id),
        ]

        for username, pwd_hash, is_admin, p_id in seed_users:
            try:
                execute_mutation(
                    "INSERT INTO usuario (username, password_hash, is_admin, perfil_id) VALUES (%s, %s, %s, %s)"
                    if mode == "postgres"
                    else "INSERT OR IGNORE INTO usuario (username, password_hash, is_admin, perfil_id) VALUES (?, ?, ?, ?)",
                    (username, pwd_hash, is_admin, p_id),
                )
            except Exception as e:
                logger.warning(f"Error seeding user {username}: {e}")

    # Seed sample employee data from CSV if employee table is empty
    employees = execute_query("SELECT id FROM employee LIMIT 1")
    csv_path = ROOT_DIR / "docs" / "Example_Table_Employee.csv"
    if not employees and csv_path.exists():
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows_to_insert = []
                for i, row in enumerate(reader):
                    if i >= 100:  # Load first 100 sample records for quick testing
                        break
                    rows_to_insert.append((
                        row.get("Education"),
                        int(row.get("JoiningYear", 0)),
                        row.get("City"),
                        int(row.get("PaymentTier", 0)),
                        int(row.get("Age", 0)),
                        row.get("Gender"),
                        row.get("EverBenched"),
                        int(row.get("ExperienceInCurrentDomain", 0)),
                        int(row.get("LeaveOrNot", 0)),
                    ))

                for r in rows_to_insert:
                    execute_mutation(
                        """INSERT INTO employee 
                        (education, joining_year, city, payment_tier, age, gender, ever_benched, experience_in_current_domain, leave_or_not)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                        if mode == "postgres"
                        else """INSERT INTO employee 
                        (education, joining_year, city, payment_tier, age, gender, ever_benched, experience_in_current_domain, leave_or_not)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        r,
                    )
        except Exception as e:
            logger.warning(f"Could not seed employee table: {e}")
