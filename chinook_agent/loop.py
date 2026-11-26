from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .llm import LLMError
from .tools import TOOL_SPECS, Toolbox

SYSTEM_PROMPT = """Ти відповідаєш на питання про дані в базі SQLite Chinook.
Працюй через інструменти: get_schema, run_sql, final_answer.
Правила:
- спершу подивись схему, якщо не впевнений у назвах таблиць і колонок;
- run_sql приймає один SELECT; запити на запис відхиляються;
- LIMIT додається автоматично, якщо його немає; результат може бути обрізаний;
- помилка запиту приходить як результат інструмента: виправ запит і спробуй ще;
- не вигадуй значень: бери їх із результатів запитів;
- коли маєш відповідь, виклич final_answer;
- у тексті відповіді наведи точні значення: числа як числа, назви як у базі;
- відповідь українською, коротко, без переказу всього запиту.
"""


@dataclass
class AgentResult:
    answer: str | None
    steps: int
    tool_calls: int
    sql_calls: int
    sql_errors: int
    limit_reached: bool
    finished_via: str | None
    error: str | None
    messages: list[dict[str, Any]] = field(default_factory=list)


def run_agent(question: str, client, toolbox: Toolbox, max_steps: int) -> AgentResult:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Порожнє питання")
    if max_steps <= 0:
        raise ValueError("max_steps має бути > 0")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question.strip()},
    ]
    steps = tool_calls = sql_calls = sql_errors = 0
    answer: str | None = None
    finished_via: str | None = None
    error: str | None = None

    for step in range(1, max_steps + 1):
        steps = step
        try:
            result = client.chat(messages, tools=TOOL_SPECS)
        except LLMError as exc:
            error = str(exc)
            break

        messages.append(result.message)
        calls = result.message.get("tool_calls") or []
        if not calls:
            content = (result.message.get("content") or "").strip()
            if content:
                answer, finished_via = content, "content"
            else:
                error = "модель не повернула ні тексту, ні виклику інструмента"
            break

        for call in calls:
            tool_calls += 1
            function = call.get("function") or {}
            name = function.get("name") or ""
            if answer is not None:
                # Виклик не виконувався, тому в sql_calls і sql_errors він не потрапляє.
                skipped = '{"ok": false, "error": "не виконано: роботу вже завершено"}'
                messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": skipped})
                continue
            content, meta = toolbox.call(name, function.get("arguments") or "{}")
            if meta.get("tool") == "run_sql":
                sql_calls += 1
                sql_errors += 0 if meta.get("ok") else 1
            if meta.get("final_answer"):
                answer, finished_via = meta["final_answer"], "tool"
            messages.append(
                {"role": "tool", "tool_call_id": call.get("id"), "content": content}
            )

        if answer is not None:
            break

    return AgentResult(
        answer=answer,
        steps=steps,
        tool_calls=tool_calls,
        sql_calls=sql_calls,
        sql_errors=sql_errors,
        limit_reached=answer is None and error is None,
        finished_via=finished_via,
        error=error,
        messages=messages,
    )
