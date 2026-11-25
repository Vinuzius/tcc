import pytest

from app.privacy_engine import PrivacyEngine

SCHEMA = {
    "employee": {
        "education": "varchar",
        "joining_year": "integer",
        "city": "varchar",
        "payment_tier": "integer",
        "age": "integer",
        "gender": "varchar",
        "ever_benched": "varchar",
        "experience_in_current_domain": "integer",
        "leave_or_not": "integer",
    }
}


def _make_engine() -> PrivacyEngine:
    return PrivacyEngine(
        arani_query=lambda sql, params=None: [],
        source_query=lambda sql, max_rows=None: [],
    )


def test_analyze_query_alias_expression_and_function() -> None:
    engine = _make_engine()

    assert engine.analyze_query("SELECT city AS c FROM employee", SCHEMA) == {
        "c": {("employee", "city")}
    }
    assert engine.analyze_query("SELECT city || '-' || age AS x FROM employee", SCHEMA) == {
        "x": {("employee", "city"), ("employee", "age")}
    }
    assert engine.analyze_query("SELECT UPPER(city) AS u FROM employee", SCHEMA) == {
        "u": {("employee", "city")}
    }


def test_analyze_query_subquery_cte_join_and_star() -> None:
    engine = _make_engine()

    assert engine.analyze_query(
        "SELECT t.c FROM (SELECT city AS c FROM employee) t", SCHEMA
    ) == {"c": {("employee", "city")}}

    assert engine.analyze_query(
        "WITH cte AS (SELECT city AS c FROM employee) SELECT UPPER(c) AS u FROM cte",
        SCHEMA,
    ) == {"u": {("employee", "city")}}

    assert engine.analyze_query(
        "SELECT a.city, b.age FROM employee a JOIN employee b ON a.age = b.age",
        SCHEMA,
    ) == {
        "city": {("employee", "city")},
        "age": {("employee", "age")},
    }

    star_lineage = engine.analyze_query("SELECT * FROM employee", SCHEMA)
    assert set(star_lineage.keys()) == set(SCHEMA["employee"].keys())
    assert star_lineage["city"] == {("employee", "city")}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM app_user",
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.columns",
        "SELECT city FROM employee UNION SELECT city FROM employee",
        "SELECT city FROM employee; SELECT age FROM employee",
        "DELETE FROM employee",
        "SELECT version()",
        "SELECT 1",
    ],
)
def test_analyze_query_rejects_unsafe_or_unknown_queries(sql: str) -> None:
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.analyze_query(sql, SCHEMA)


def test_apply_rules_conservative_and_classified_coverage() -> None:
    engine = _make_engine()
    lineage_map = {
        "x": {("employee", "city"), ("employee", "age")},
        "education": {("employee", "education")},
    }
    rules = {
        ("employee", "city"): [
            {"rule_id": 1, "table_name": "employee", "column_name": "city", "algorithm": "UPPER", "params": {}}
        ]
    }
    classified = {("employee", "education")}  # sem regra que a proteja -> oculta

    rows, applied, columns = engine.apply_rules(
        [{"x": "Bangalore-25", "education": "Bachelors"}],
        lineage_map,
        rules,
        classified,
    )
    assert columns == ["x"]
    assert rows == [{"x": "BANGALORE-25"}]
    assert len(applied) == 1


def test_apply_rules_raises_permission_error_when_no_columns_remain() -> None:
    engine = _make_engine()
    lineage_map = {"education": {("employee", "education")}}
    rules = {
        ("employee", "education"): [
            {"rule_id": 2, "table_name": "employee", "column_name": "education", "algorithm": "HIDE_COLUMN", "params": {}}
        ]
    }
    with pytest.raises(PermissionError, match="Nenhuma coluna permitida"):
        engine.apply_rules([], lineage_map, rules, set())


def test_execute_rejects_user_without_profile() -> None:
    called = False

    def fail_if_called(sql: str, max_rows: int | None = None):
        nonlocal called
        called = True
        return []

    engine = PrivacyEngine(arani_query=lambda sql, params=None: [], source_query=fail_if_called)
    with pytest.raises(PermissionError, match="Usuário sem perfil atribuído"):
        engine.execute({"id": 1, "profile_id": None}, "SELECT city FROM employee")
    assert called is False
