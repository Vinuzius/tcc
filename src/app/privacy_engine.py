"""Intermediário de privacidade: aplica no resultado as regras do perfil do usuário.

Fluxo:
  1. valida que o SQL é read-only
  2. executa o SQL na fonte de dados (o banco que o usuário conhece)
  3. busca no Arani as regras do perfil do usuário
  4. transforma o resultado conforme as regras (coluna sem regra = valor original)
  5. registra a execução no Arani (auditoria)
"""
from typing import Any, Callable

QueryFn = Callable[..., list[dict[str, Any]]]


HIDDEN = object()  # marcador: a coluna deve sair do resultado


class PrivacyEngine:
    def __init__(self, arani_query: QueryFn, source_query: QueryFn) -> None:
        # arani_query: conexão do Arani (leitura/escrita)
        # source_query: conexão da fonte de dados (SOMENTE LEITURA)
        self.arani_query = arani_query
        self.source_query = source_query
        self.algorithms: dict[str, Callable[[Any, dict], Any]] = {
            "UPPER": self._upper,
            "MASK": self._mask,
            "SUPPRESS": self._suppress,
            "HIDE_COLUMN": self._hide,
        }

    # ---------- algoritmos ----------
    @staticmethod
    def _upper(value: Any, params: dict) -> Any:
        return value.upper() if isinstance(value, str) else value

    @staticmethod
    def _mask(value: Any, params: dict) -> Any:
        if value is None:
            return None
        text, keep = str(value), int(params.get("keep_last", 0))
        return "*" * max(len(text) - keep, 0) + (text[-keep:] if keep else "")

    @staticmethod
    def _suppress(value: Any, params: dict) -> Any:
        return None

    @staticmethod
    def _hide(value: Any, params: dict) -> Any:
        return HIDDEN

    # ---------- regras ----------
    def get_rules(self, profile_id: int) -> list[dict[str, Any]]:
        return self.arani_query(
            """
            SELECT pr.id AS rule_id, dt.name AS table_name, dc.name AS column_name,
                   a.name AS algorithm, pr.params, pr.attribute_set_id
            FROM arani.profile_rule pr
            JOIN arani.algorithm a             ON a.id = pr.algorithm_id
            JOIN arani.attribute_set_column sc ON sc.attribute_set_id = pr.attribute_set_id
            JOIN arani.data_column dc          ON dc.id = sc.data_column_id
            JOIN arani.data_table dt           ON dt.id = dc.data_table_id
            WHERE pr.profile_id = %s
            ORDER BY pr.id
            """,
            (profile_id,),
        )

    def apply_rules(self, rows: list[dict], rules: list[dict]) -> tuple[list[dict], list[dict]]:
        """Retorna (linhas transformadas, regras efetivamente aplicadas)."""
        if not rows:
            return rows, []

        by_column: dict[str, list[dict]] = {}
        for rule in rules:
            by_column.setdefault(rule["column_name"].lower(), []).append(rule)

        # TODO: limitação conhecida — a engine casa as regras pelo nome da coluna do resultado,
        # então aliases como `SELECT city AS c FROM employee` não aplicam a regra.
        # só as colunas presentes no resultado
        active = {col: by_column[col.lower()] for col in rows[0] if col.lower() in by_column}
        applied = [r for rs in active.values() for r in rs]

        for rule in applied:  # falha fechada: algoritmo desconhecido não vaza dado
            if rule["algorithm"] not in self.algorithms:
                raise ValueError(f"Unknown algorithm: {rule['algorithm']}")

        result = []
        for row in rows:
            new_row = dict(row)
            for col, col_rules in active.items():
                for rule in col_rules:
                    new_row[col] = self.algorithms[rule["algorithm"]](new_row[col], rule["params"] or {})
                    if new_row[col] is HIDDEN:
                        break
                if new_row[col] is HIDDEN:
                    del new_row[col]
            result.append(new_row)
        return result, applied

    # ---------- fluxo principal ----------
    def execute(self, user: dict[str, Any], sql: str) -> dict[str, Any]:
        from database.queries import ensure_read_query  # validação já existente no projeto

        statement = ensure_read_query(sql)
        rows = self.source_query(statement)
        rules = self.get_rules(user["profile_id"]) if user.get("profile_id") else []
        rows, applied = self.apply_rules(rows, rules)
        self._log_execution(user, statement, applied)
        return {
            "columns": list(rows[0].keys()) if rows else [],
            "rows": rows,
            "row_count": len(rows),
        }

    def _log_execution(self, user: dict, sql: str, applied: list[dict]) -> None:
        execution = self.arani_query(
            """
            INSERT INTO arani.query_execution (user_id, profile_id, sql_query, status, started_at, finished_at)
            VALUES (%s, %s, %s, 'SUCCEEDED', now(), now()) RETURNING id
            """,
            (user["id"], user.get("profile_id"), sql),
        )
        execution_id = execution[0]["id"]
        # a ordem das etapas é definida aqui, pela API (sequence = 1, 2, 3...)
        for sequence, rule in enumerate(applied, start=1):
            self.arani_query(
                """
                INSERT INTO arani.execution_step
                    (query_execution_id, sequence, algorithm_id, attribute_set_id, profile_rule_id, params)
                SELECT %s, %s, pr.algorithm_id, pr.attribute_set_id, pr.id, pr.params
                FROM arani.profile_rule pr WHERE pr.id = %s
                RETURNING sequence
                """,
                (execution_id, sequence, rule["rule_id"]),
            )
