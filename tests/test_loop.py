import json

import pytest
from conftest import assistant, tool_call

from chinook_agent.loop import run_agent


def test_final_answer_stops_loop(scripted, toolbox):
    client = scripted([
        assistant([tool_call("run_sql", '{"query": "SELECT COUNT(*) FROM Artist"}')]),
        assistant([tool_call("final_answer", '{"text": "2 артисти"}', "c2")]),
    ])
    result = run_agent("Скільки артистів?", client, toolbox, max_steps=8)
    assert result.answer == "2 артисти"
    assert result.steps == 2 and result.tool_calls == 2
    assert result.sql_calls == 1 and result.sql_errors == 0
    assert result.limit_reached is False and result.finished_via == "tool"


def test_step_limit_stops_without_answer(scripted, toolbox):
    call = assistant([tool_call("run_sql", '{"query": "SELECT 1"}')])
    client = scripted([call, call, call])
    result = run_agent("Питання?", client, toolbox, max_steps=3)
    assert result.answer is None
    assert result.steps == 3 and result.limit_reached is True
    assert len(client.calls) == 3


def test_sql_error_is_returned_to_model(scripted, toolbox):
    client = scripted([
        assistant([tool_call("run_sql", '{"query": "DROP TABLE Artist"}')]),
        assistant([tool_call("final_answer", '{"text": "Не можу"}', "c2")]),
    ])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.sql_errors == 1
    tool_message = client.calls[1][-1]
    assert tool_message["role"] == "tool" and tool_message["tool_call_id"] == "c1"
    assert json.loads(tool_message["content"])["ok"] is False
    assert "лише SELECT" in tool_message["content"]


def test_plain_content_counts_as_answer(scripted, toolbox):
    client = scripted([assistant(content="2 артисти")])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.answer == "2 артисти" and result.finished_via == "content"
    assert result.tool_calls == 0


def test_empty_response_is_error(scripted, toolbox):
    client = scripted([assistant()])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.answer is None and result.error is not None
    assert result.limit_reached is False


def test_calls_after_final_answer_are_skipped(scripted, toolbox):
    client = scripted([
        assistant([
            tool_call("final_answer", '{"text": "готово"}', "c1"),
            tool_call("run_sql", '{"query": "SELECT 1"}', "c2"),
        ])
    ])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.answer == "готово"
    assert result.tool_calls == 2 and result.sql_calls == 0


def test_unknown_tool_does_not_crash(scripted, toolbox):
    client = scripted([
        assistant([tool_call("hack", "{}")]),
        assistant([tool_call("final_answer", '{"text": "кінець"}', "c2")]),
    ])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.answer == "кінець" and result.error is None


def test_multiple_tool_calls_in_one_step(scripted, toolbox):
    client = scripted([
        assistant([
            tool_call("get_schema", "{}", "c1"),
            tool_call("run_sql", '{"query": "SELECT 1"}', "c2"),
        ]),
        assistant([tool_call("final_answer", '{"text": "1"}', "c3")]),
    ])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.steps == 2 and result.tool_calls == 3


@pytest.mark.parametrize("question", ["", "   "])
def test_empty_question_rejected(scripted, toolbox, question):
    with pytest.raises(ValueError):
        run_agent(question, scripted([]), toolbox, max_steps=8)


def test_invalid_max_steps(scripted, toolbox):
    with pytest.raises(ValueError):
        run_agent("Питання?", scripted([]), toolbox, max_steps=0)


def test_skipped_call_does_not_inflate_sql_error_count(scripted, toolbox):
    client = scripted([
        assistant([
            tool_call("final_answer", '{"text": "готово"}', "c1"),
            tool_call("run_sql", '{"query": "SELECT 1"}', "c2"),
        ])
    ])
    result = run_agent("Питання?", client, toolbox, max_steps=8)
    assert result.sql_calls == 0 and result.sql_errors == 0
    skipped = [m for m in result.messages if m.get("tool_call_id") == "c2"]
    assert len(skipped) == 1 and "не виконано" in skipped[0]["content"]
