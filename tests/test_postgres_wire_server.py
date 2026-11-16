import postgres_wire_server


def test_query_decodes_wire_protocol_bytes(monkeypatch) -> None:
    monkeypatch.setattr(
        postgres_wire_server,
        "execute_read_query",
        lambda sql: [{"education": "Bachelors", "city": "Bangalore", "payment_tier": 1}],
    )

    handler = object.__new__(postgres_wire_server.EmployeeQueryHandler)

    rows = handler.query(b"SELECT education, city, payment_tier FROM employee;\x00")

    assert rows[0].city == "Bangalore"


def test_empty_wire_query_sends_completion_without_indexing_rows(monkeypatch) -> None:
    monkeypatch.setattr(postgres_wire_server, "execute_read_query", lambda sql: [])
    handler = object.__new__(postgres_wire_server.EmployeeQueryHandler)
    events = []
    handler.send_row_description = lambda fields: events.append(("description", fields))
    handler.send_row_data = lambda rows: events.append(("rows", rows))
    handler.send_command_complete = lambda tag: events.append(("complete", tag))

    handler.handle_query(b"SELECT 1;\x00")

    assert events == [
        ("description", []),
        ("rows", []),
        ("complete", b"SELECT\x00"),
    ]