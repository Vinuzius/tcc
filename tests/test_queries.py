import pytest

from database.queries import ensure_read_query


def test_ensure_read_query_accepts_select_and_trailing_semicolon() -> None:
    assert ensure_read_query(" SELECT 1; ") == "SELECT 1"


@pytest.mark.parametrize(
    "sql",
    ["", "UPDATE employee SET age = 21", "SELECT 1; SELECT 2"],
)
def test_ensure_read_query_rejects_non_read_queries(sql: str) -> None:
    with pytest.raises(ValueError):
        ensure_read_query(sql)
