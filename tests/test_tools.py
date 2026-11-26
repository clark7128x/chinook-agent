import json

from chinook_agent.tools import TOOL_NAMES


def content_json(content: str) -> dict:
    return json.loads(content)


def test_tool_specs_cover_three_tools():
    assert TOOL_NAMES == ("get_schema", "run_sql", "final_answer")


def test_get_schema_without_argument(toolbox):
    content, meta = toolbox.call("get_schema", "{}")
    assert meta["ok"] is True and "Album(" in content


def test_get_schema_unknown_table(toolbox):
    content, meta = toolbox.call("get_schema", '{"table": "Nope"}')
    assert meta["ok"] is False
    assert "невідома таблиця" in content_json(content)["error"]


def test_run_sql_success_payload(toolbox):
    content, meta = toolbox.call("run_sql", '{"query": "SELECT COUNT(*) FROM Artist"}')
    payload = content_json(content)
    assert meta == {"tool": "run_sql", "ok": True}
    assert payload["rows"] == [[2]] and payload["limit_added"] is True


def test_run_sql_error_is_data(toolbox):
    content, meta = toolbox.call("run_sql", '{"query": "DELETE FROM Artist"}')
    assert meta["ok"] is False
    assert content_json(content)["ok"] is False


def test_run_sql_requires_string_query(toolbox):
    content, meta = toolbox.call("run_sql", '{"query": 42}')
    assert meta["ok"] is False and "рядком" in content_json(content)["error"]


def test_final_answer_returns_text(toolbox):
    content, meta = toolbox.call("final_answer", '{"text": "  2 артисти  "}')
    assert meta["final_answer"] == "2 артисти"
    assert content_json(content)["ok"] is True


def test_final_answer_rejects_empty(toolbox):
    _, meta = toolbox.call("final_answer", '{"text": "   "}')
    assert meta["ok"] is False and "final_answer" not in meta


def test_unknown_tool_and_broken_arguments(toolbox):
    _, meta = toolbox.call("hack", "{}")
    assert meta["ok"] is False
    _, meta = toolbox.call("run_sql", "{не json")
    assert meta["ok"] is False
    _, meta = toolbox.call("run_sql", "[]")
    assert meta["ok"] is False


def test_arguments_may_be_dict(toolbox):
    _, meta = toolbox.call("run_sql", {"query": "SELECT 1"})
    assert meta["ok"] is True
