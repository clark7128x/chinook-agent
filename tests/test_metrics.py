import pytest

from chinook_agent.metrics import by_level, percentile, summarize


def record(level="single", solved=True, strict=True, steps=2, tools=3, sql=2, errors=0,
           limit=False, error=None, latency=1.0, recall=1.0):
    return {
        "level": level, "solved": solved, "strict_solved": strict, "steps": steps,
        "tool_calls": tools, "sql_calls": sql, "sql_errors": errors, "limit_reached": limit,
        "error": error, "latency_s": latency, "value_recall": recall,
    }


def test_summarize_normal():
    records = [record(), record(solved=False, strict=False, limit=True, recall=0.5),
               record(level="join", errors=1, sql=1)]
    summary = summarize(records, cost_total=3.0)
    assert summary["tasks"] == 3
    assert summary["solved_rate"] == pytest.approx(2 / 3)
    assert summary["limit_rate"] == pytest.approx(1 / 3)
    assert summary["sql_error_rate"] == pytest.approx(1 / 5)
    assert summary["avg_steps"] == pytest.approx(2.0)
    assert summary["cost_per_task"] == pytest.approx(1.0)


def test_summarize_empty_returns_none():
    summary = summarize([])
    assert summary["tasks"] == 0
    assert summary["solved_rate"] is None
    assert summary["sql_error_rate"] is None
    assert summary["cost_per_task"] is None
    assert summary["latency_s"]["p95"] is None


def test_no_sql_calls_gives_none_rate():
    assert summarize([record(sql=0, tools=1)])["sql_error_rate"] is None


def test_cost_none_without_prices():
    assert summarize([record()], cost_total=None)["cost_per_task"] is None


def test_failed_tasks_counted():
    assert summarize([record(error="http 500")])["failed_tasks"] == 1


def test_by_level_splits_and_allocates_cost():
    records = [record("single"), record("join"), record("join")]
    groups = by_level(records, ("single", "join", "aggregate"), cost_total=3.0)
    assert groups["single"]["tasks"] == 1
    assert groups["join"]["tasks"] == 2
    assert groups["aggregate"]["tasks"] == 0
    assert groups["aggregate"]["solved_rate"] is None
    assert groups["join"]["cost_total"] == pytest.approx(2.0)


def test_by_level_empty_records():
    groups = by_level([], ("single",), cost_total=None)
    assert groups["single"]["cost_total"] is None


@pytest.mark.parametrize("values,p,expected", [([1.0], 95, 1.0), ([1.0, 3.0], 50, 1.0), ([], 50, None)])
def test_percentile(values, p, expected):
    assert percentile(values, p) == expected


def test_percentile_invalid():
    with pytest.raises(ValueError):
        percentile([1.0], -1)
