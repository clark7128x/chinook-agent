from chinook_agent.metrics import by_level, summarize
from chinook_agent.report import MISSING, render_markdown


def payload(records, cost=None):
    return {
        "model": "m",
        "dataset": {"path": "data/tasks.jsonl", "rows": len(records), "skipped": 0},
        "overall": summarize(records, cost),
        "by_level": by_level(records, ("single", "join", "aggregate"), cost),
        "calls": {"calls": 0, "failed": 0, "input_tokens": None, "output_tokens": None,
                  "latency_p50_s": None, "latency_p95_s": None, "cost": cost},
    }


def test_empty_run_is_unmeasured():
    markdown = render_markdown(payload([]))
    assert markdown.count(MISSING) >= 10
    assert "| Рівень | Задач |" in markdown


def test_measured_values_are_formatted():
    records = [{
        "level": "single", "solved": True, "strict_solved": True, "steps": 2, "tool_calls": 3,
        "sql_calls": 1, "sql_errors": 0, "limit_reached": False, "error": None,
        "latency_s": 1.0, "value_recall": 1.0,
    }]
    markdown = render_markdown(payload(records, cost=0.5))
    assert "1.000" in markdown and "0.5000" in markdown and "1000" in markdown


def test_skip_reason_is_shown():
    data = payload([])
    data["skipped_reason"] = "не задано LLM_MODEL"
    assert "Пропущено: не задано LLM_MODEL." in render_markdown(data)


def test_all_levels_present():
    markdown = render_markdown(payload([]))
    for level in ("single", "join", "aggregate", "усі"):
        assert f"| {level} |" in markdown
