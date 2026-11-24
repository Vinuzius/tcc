"""Conexões com o PostgreSQL.

Duas conexões separadas, que nunca se misturam:
  - Arani:  banco da própria API (usuários, perfis, regras, auditoria). Leitura e escrita.
  - Source: fonte de dados que os usuários consultam (ex.: employee).
            SOMENTE LEITURA, com papel restrito (source_reader).

Uma conexão curta por chamada (suficiente para o MVP).
"""
import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=True)


def _connect(prefix: str, default_schema: str, read_only: bool) -> psycopg.Connection:
    schema = os.getenv(f"{prefix}_SCHEMA", default_schema)
    conn = psycopg.connect(
        host=os.getenv(f"{prefix}_HOST", "localhost"),
        port=os.getenv(f"{prefix}_PORT", "5432"),
        dbname=os.getenv(f"{prefix}_NAME", "postgres"),
        user=os.getenv(f"{prefix}_USER"),
        password=os.getenv(f"{prefix}_PASSWORD"),
        options=f"-c search_path={schema}",
    )
    if read_only:
        conn.read_only = True  # toda transação desta conexão começa como READ ONLY
    return conn


def get_arani_connection() -> psycopg.Connection:
    return _connect("ARANI_DB", default_schema="arani", read_only=False)


def get_source_connection() -> psycopg.Connection:
    return _connect("SOURCE_DB", default_schema="public", read_only=True)


def _fetch(conn: psycopg.Connection, sql: str, params: tuple | list | None) -> list[dict[str, Any]]:
    # params=None (e não ()) mantém o '%' do SQL do usuário (ex.: LIKE 'A%') sem interpretação
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return []
        return list(cur.fetchall())


def arani_query(sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    """Executa SQL no Arani (também serve para INSERT ... RETURNING). Faz commit ao sair."""
    with get_arani_connection() as conn:
        return _fetch(conn, sql, params)


def arani_mutation(sql: str, params: tuple | list | None = None) -> int:
    """Executa INSERT/UPDATE/DELETE no Arani e devolve o número de linhas afetadas."""
    with get_arani_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


def source_query(sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    """Executa SQL na fonte de dados, em transação READ ONLY e com o papel restrito."""
    with get_source_connection() as conn:
        return _fetch(conn, sql, params)


def run_arani_script(path: Path) -> None:
    """Executa um arquivo .sql inteiro no Arani (schema/seed). O arquivo controla BEGIN/COMMIT."""
    script = path.read_text(encoding="utf-8")
    with get_arani_connection() as conn:
        conn.autocommit = True
        conn.execute(script)
