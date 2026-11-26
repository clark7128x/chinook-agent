from __future__ import annotations

MISSING = "не виміряно"


def _fmt(value, spec: str = "{:.3f}") -> str:
    return MISSING if value is None else spec.format(value)


def _ms(value) -> str:
    return MISSING if value is None else f"{value * 1000:.0f}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _row(name: str, metrics: dict) -> list[str]:
    return [
        name,
        str(metrics.get("tasks", 0)),
        _fmt(metrics.get("solved_rate")),
        _fmt(metrics.get("strict_solved_rate")),
        _fmt(metrics.get("avg_steps"), "{:.2f}"),
        _fmt(metrics.get("avg_tool_calls"), "{:.2f}"),
        _fmt(metrics.get("limit_rate")),
        _fmt(metrics.get("sql_error_rate")),
        _fmt(metrics.get("cost_per_task"), "{:.4f}"),
    ]


def render_markdown(payload: dict) -> str:
    dataset = payload.get("dataset", {})
    overall = payload.get("overall", {})
    levels = payload.get("by_level", {})
    lines = [
        "# Результати оцінки",
        "",
        f"Набір: `{dataset.get('path', '—')}`. Задач: {dataset.get('rows', 0)}. "
        f"Пропущено: {dataset.get('skipped', 0)}.",
        "",
        "## Розв'язання за рівнями",
        "",
    ]
    header = ["Рівень", "Задач", "Частка", "Строга частка", "Сер. кроків",
              "Сер. викликів", "Ліміт кроків", "Помилки SQL", "Вартість/задачу"]
    lines += _table(header, [_row(level, metrics) for level, metrics in levels.items()]
                    + [_row("усі", overall)])

    lines += ["", "## Затримка й виклики", ""]
    latency = overall.get("latency_s") or {}
    calls = payload.get("calls") or {}
    lines += _table(
        ["Модель", "Викликів", "Помилок", "Вхідні токени", "Вихідні токени",
         "p50 задачі, мс", "p95 задачі, мс", "Вартість"],
        [[
            payload.get("model") or "—",
            _fmt(calls.get("calls"), "{:.0f}"),
            _fmt(calls.get("failed"), "{:.0f}"),
            _fmt(calls.get("input_tokens"), "{:.0f}"),
            _fmt(calls.get("output_tokens"), "{:.0f}"),
            _ms(latency.get("p50")),
            _ms(latency.get("p95")),
            _fmt(calls.get("cost"), "{:.4f}"),
        ]],
    )

    lines += ["", "## Часткове покриття значень", ""]
    lines += _table(
        ["Рівень", "Середня value_recall", "Задач з помилкою агента"],
        [[level, _fmt(metrics.get("value_recall_mean")), str(metrics.get("failed_tasks", 0))]
         for level, metrics in levels.items()],
    )

    if payload.get("skipped_reason"):
        lines += ["", f"Пропущено: {payload['skipped_reason']}."]
    return "\n".join(lines) + "\n"
