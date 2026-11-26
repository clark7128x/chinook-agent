from __future__ import annotations

import math
from typing import Sequence


def percentile(values: Sequence[float], p: float) -> float | None:
    if not 0 <= p <= 100:
        raise ValueError("p має бути в [0, 100]")
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(p / 100 * len(ordered)) - 1)
    return float(ordered[index])


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(records: list[dict], cost_total: float | None = None) -> dict:
    tasks = len(records)
    sql_calls = sum(record["sql_calls"] for record in records)
    sql_errors = sum(record["sql_errors"] for record in records)
    latencies = [record["latency_s"] for record in records if record.get("latency_s") is not None]
    recalls = [record["value_recall"] for record in records if record.get("value_recall") is not None]
    return {
        "tasks": tasks,
        "solved": sum(1 for record in records if record["solved"]),
        "solved_rate": _rate(sum(1 for record in records if record["solved"]), tasks),
        "strict_solved_rate": _rate(sum(1 for record in records if record["strict_solved"]), tasks),
        "value_recall_mean": _mean(recalls),
        "avg_steps": _mean([record["steps"] for record in records]),
        "avg_tool_calls": _mean([record["tool_calls"] for record in records]),
        "limit_reached": sum(1 for record in records if record["limit_reached"]),
        "limit_rate": _rate(sum(1 for record in records if record["limit_reached"]), tasks),
        "failed_tasks": sum(1 for record in records if record.get("error")),
        "sql_calls": sql_calls,
        "sql_errors": sql_errors,
        "sql_error_rate": _rate(sql_errors, sql_calls),
        "cost_total": cost_total,
        "cost_per_task": cost_total / tasks if cost_total is not None and tasks else None,
        "latency_s": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "mean": _mean(latencies),
        },
    }


def by_level(records: list[dict], levels: Sequence[str], cost_total: float | None = None) -> dict:
    groups = {level: [record for record in records if record["level"] == level] for level in levels}
    total_tasks = len(records)
    result = {}
    for level, group in groups.items():
        share = len(group) / total_tasks if total_tasks else None
        level_cost = cost_total * share if cost_total is not None and share is not None else None
        result[level] = summarize(group, level_cost)
    return result
