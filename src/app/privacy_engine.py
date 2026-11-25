"""Intermediário de privacidade: aplica no resultado as regras do perfil do usuário.

Fluxo:
  1. valida que o SQL é read-only e analisa a linhagem das colunas com sqlglot
  2. executa o SQL na fonte de dados (somente leitura, com limite QUERY_MAX_ROWS)
  3. busca no Arani a política do perfil (regras conformes + colunas classificadas)
  4. transforma o resultado conforme as regras e oculta colunas classificadas sem proteção
  5. registra a execução no Arani (auditoria)
"""
from typing import Any, Callable

import sqlglot
from sqlglot import exp
from sqlglot.lineage import lineage
from sqlglot.optimizer.qualify import qualify

from database.connections import get_query_max_rows
from database.queries import ensure_read_query

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

    # ---------- catálogo e linhagem ----------
    def get_catalog_schema(self) -> dict[str, dict[str, str]]:
        """Carrega o catálogo (tabelas e colunas) da fonte de dados a partir do Arani."""
        rows = self.arani_query(
            """
            SELECT dt.name AS table_name, dc.name AS column_name, dc.data_type
            FROM arani.data_table dt
            JOIN arani.data_column dc ON dc.data_table_id = dt.id
            ORDER BY dt.id, dc.id
            """
        )
        schema: dict[str, dict[str, str]] = {}
        for row in rows:
            table_name = row["table_name"].lower()
            col_name = row["column_name"].lower()
            schema.setdefault(table_name, {})[col_name] = row["data_type"]
        return schema

    @staticmethod
    def _extract_source_columns(
        col_name: str,
        qualified: exp.Select,
        catalog_schema: dict[str, dict[str, str]],
    ) -> set[tuple[str, str]]:
        """Rastreia de qual(is) coluna(s) real(is) da fonte uma coluna do resultado deriva."""
        node = lineage(col_name, qualified, schema=catalog_schema, dialect="postgres")
        sources: set[tuple[str, str]] = set()
        for leaf in node.walk():
            if leaf.downstream or not isinstance(leaf.expression, exp.Table):
                continue
            src_table = leaf.expression.name.lower()
            parsed_col = sqlglot.parse_one(leaf.name, read="postgres")
            if not isinstance(parsed_col, exp.Column) or not parsed_col.name:
                continue
            src_col = parsed_col.name.lower()
            if src_table in catalog_schema and src_col in catalog_schema[src_table]:
                sources.add((src_table, src_col))
        return sources

    def analyze_query(
        self,
        sql: str,
        catalog_schema: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, set[tuple[str, str]]]:
        """Valida a consulta (fail closed) e retorna o mapeamento coluna_resultado -> {(tabela, coluna)}."""
        statement = ensure_read_query(sql)

        try:
            trees = sqlglot.parse(statement, read="postgres")
        except Exception as exc:
            raise ValueError(f"Consulta SQL inválida: {exc}") from exc

        if len(trees) != 1 or trees[0] is None:
            raise ValueError("Apenas uma instrução SQL SELECT é permitida")

        tree = trees[0]
        if not isinstance(tree, exp.Select):
            raise ValueError("Apenas consultas SELECT são permitidas")

        if any(tree.find_all((exp.Union, exp.Intersect, exp.Except, exp.SetOperation))):
            raise ValueError("Operações de conjunto (UNION, INTERSECT, EXCEPT) não são permitidas")

        if any(tree.find_all((exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Command))):
            raise ValueError("Apenas consultas de leitura são permitidas")

        schema = catalog_schema if catalog_schema is not None else self.get_catalog_schema()
        if not schema:
            raise ValueError("Catálogo de dados vazio; nenhuma tabela disponível para consulta")

        cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE) if cte.alias_or_name}
        for table in tree.find_all(exp.Table):
            tbl_db = (table.db or "").lower()
            tbl_name = (table.name or "").lower()
            if tbl_db:
                if tbl_db != "public" or tbl_name not in schema:
                    raise ValueError(f"Tabela não autorizada ou fora do catálogo: {table.sql('postgres')}")
                table.set("db", None)
            elif tbl_name not in schema and tbl_name not in cte_names:
                raise ValueError(f"Tabela não autorizada ou fora do catálogo: {table.name}")

        try:
            qualified = qualify(tree, schema=schema, dialect="postgres")
        except Exception as exc:
            raise ValueError(f"Não foi possível analisar a consulta SQL: {exc}") from exc

        if not isinstance(qualified, exp.Select) or not qualified.expressions:
            raise ValueError("Apenas consultas SELECT com colunas explícitas são permitidas")

        column_lineage: dict[str, set[tuple[str, str]]] = {}
        for sel in qualified.expressions:
            col_name = sel.alias_or_name
            if isinstance(sel, exp.Star) or not col_name or col_name == "*":
                raise ValueError("Não foi possível determinar a origem da coluna '*'")
            try:
                sources = self._extract_source_columns(col_name, qualified, schema)
            except Exception as exc:
                raise ValueError(f"Não foi possível determinar a origem da coluna '{col_name}': {exc}") from exc

            if not sources:
                raise ValueError(f"Não foi possível determinar a origem da coluna '{col_name}'")

            column_lineage.setdefault(col_name, set()).update(sources)

        return column_lineage

    # ---------- políticas e regras ----------
    def get_policy(
        self, profile_id: int
    ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], set[tuple[str, str]]]:
        """Retorna (regras_conformes_por_coluna, colunas_classificadas) para o perfil."""
        # Revalida na execução: uma regra só vale se a garantia do algoritmo satisfizer
        # CADA classificação aplicável do conjunto (regulação + classificação própria do perfil).
        rule_rows = self.arani_query(
            """
            SELECT pr.id AS rule_id,
                   dt.name AS table_name,
                   dc.name AS column_name,
                   a.name AS algorithm,
                   pr.params,
                   pr.attribute_set_id
            FROM arani.profile_rule pr
            JOIN arani.algorithm a             ON a.id = pr.algorithm_id
            JOIN arani.attribute_set_column sc ON sc.attribute_set_id = pr.attribute_set_id
            JOIN arani.data_column dc          ON dc.id = sc.data_column_id
            JOIN arani.data_table dt           ON dt.id = dc.data_table_id
            WHERE pr.profile_id = %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM arani.profile_set_classification c
                  WHERE c.profile_id = pr.profile_id
                    AND c.attribute_set_id = pr.attribute_set_id
                    AND c.privacy_classification <> 'NON_IDENTIFIER'
                    AND NOT EXISTS (
                        SELECT 1
                        FROM arani.classification_guarantee cg
                        WHERE cg.privacy_classification = c.privacy_classification
                          AND cg.guarantee = a.guarantee
                    )
              )
            ORDER BY pr.id
            """,
            (profile_id,),
        )
        rules_by_column: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for rule in rule_rows:
            key = (rule["table_name"].lower(), rule["column_name"].lower())
            rules_by_column.setdefault(key, []).append(rule)

        classified_rows = self.arani_query(
            """
            SELECT DISTINCT dt.name AS table_name, dc.name AS column_name
            FROM arani.profile_set_classification c
            JOIN arani.attribute_set_column sc ON sc.attribute_set_id = c.attribute_set_id
            JOIN arani.data_column dc          ON dc.id = sc.data_column_id
            JOIN arani.data_table dt           ON dt.id = dc.data_table_id
            WHERE c.profile_id = %s
              AND c.privacy_classification <> 'NON_IDENTIFIER'
            """,
            (profile_id,),
        )
        classified_columns = {
            (row["table_name"].lower(), row["column_name"].lower())
            for row in classified_rows
        }
        return rules_by_column, classified_columns

    def apply_rules(
        self,
        rows: list[dict[str, Any]],
        column_lineage: dict[str, set[tuple[str, str]]],
        rules_by_column: dict[tuple[str, str], list[dict[str, Any]]],
        classified_columns: set[tuple[str, str]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """Aplica regras pela coluna de origem e oculta colunas classificadas sem proteção.

        Política conservadora: se uma coluna do resultado derivar de uma coluna de origem
        coberta por regra (mesmo dentro de uma expressão), aplica a regra à coluna inteira
        do resultado. Se derivar de coluna classificada sem regra conforme, oculta a coluna.
        """
        active_rules: dict[str, list[dict[str, Any]]] = {}
        hidden_columns: set[str] = set()
        applied: list[dict[str, Any]] = []
        seen_rule_ids: set[int] = set()

        for result_col, sources in column_lineage.items():
            # Coluna classificada sem regra conforme que a proteja não pode sair crua.
            if any(src in classified_columns and not rules_by_column.get(src) for src in sources):
                hidden_columns.add(result_col)
                continue

            col_rules: list[dict[str, Any]] = []
            col_rule_ids: set[int] = set()
            for src in sorted(sources):
                for rule in rules_by_column.get(src, []):
                    if rule["rule_id"] not in col_rule_ids:
                        col_rule_ids.add(rule["rule_id"])
                        col_rules.append(rule)

            if col_rules:
                active_rules[result_col] = col_rules
                for rule in col_rules:
                    if rule["algorithm"] not in self.algorithms:
                        raise ValueError(f"Unknown algorithm: {rule['algorithm']}")
                    if rule["algorithm"] == "HIDE_COLUMN":
                        hidden_columns.add(result_col)
                    if rule["rule_id"] not in seen_rule_ids:
                        seen_rule_ids.add(rule["rule_id"])
                        applied.append(rule)

        remaining_columns = [col for col in column_lineage if col not in hidden_columns]
        if not remaining_columns:
            raise PermissionError("Nenhuma coluna permitida para o seu perfil")

        if not rows:
            return [], applied, remaining_columns

        # Mapeia chaves reais retornadas pelo driver (caso difiram apenas em caixa)
        lineage_lookup = {col.lower(): col for col in column_lineage}
        result: list[dict[str, Any]] = []
        for row in rows:
            new_row = dict(row)
            for key in list(new_row.keys()):
                col = key if key in column_lineage else lineage_lookup.get(key.lower(), key)
                if col in hidden_columns:
                    del new_row[key]
                    continue
                for rule in active_rules.get(col, []):
                    new_row[key] = self.algorithms[rule["algorithm"]](
                        new_row[key], rule["params"] or {}
                    )
                    if new_row[key] is HIDDEN:
                        del new_row[key]
                        break
            result.append(new_row)

        return result, applied, list(result[0].keys())

    # ---------- fluxo principal ----------
    def execute(self, user: dict[str, Any], sql: str) -> dict[str, Any]:
        if not user.get("profile_id"):
            raise PermissionError("Usuário sem perfil atribuído")

        statement = ensure_read_query(sql)
        column_lineage = self.analyze_query(statement)

        max_rows = get_query_max_rows()
        rows = self.source_query(statement, max_rows=max_rows + 1)

        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]

        rules_by_column, classified_columns = self.get_policy(user["profile_id"])
        rows, applied, columns = self.apply_rules(
            rows, column_lineage, rules_by_column, classified_columns
        )
        self._log_execution(user, statement, applied)
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
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
