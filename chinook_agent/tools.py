from __future__ import annotations

import json
from typing import Any

from .database import ReadOnlyDatabase

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "Повертає схеми таблиць бази Chinook. Без аргументу — усі таблиці.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Назва таблиці, наприклад Album"}
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": (
                "Виконує один SELECT у read-only з'єднанні. "
                "LIMIT додається автоматично, якщо його немає. Помилка повертається як результат."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "SQL-запит SELECT"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": "Завершує роботу й повертає відповідь користувачу українською.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_NAMES = tuple(spec["function"]["name"] for spec in TOOL_SPECS)


def _error(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


class Toolbox:
    def __init__(self, database: ReadOnlyDatabase):
        self.database = database

    def call(self, name: str, arguments: str | dict) -> tuple[str, dict]:
        if isinstance(arguments, str):
            try:
                payload = json.loads(arguments or "{}")
            except json.JSONDecodeError as exc:
                return _error(f"аргументи не є JSON: {exc}"), {"tool": name, "ok": False}
        else:
            payload = arguments
        if not isinstance(payload, dict):
            return _error("аргументи мають бути JSON-об'єктом"), {"tool": name, "ok": False}

        if name == "get_schema":
            return self._get_schema(payload)
        if name == "run_sql":
            return self._run_sql(payload)
        if name == "final_answer":
            return self._final_answer(payload)
        return _error(f"невідомий інструмент {name!r}; доступні: {', '.join(TOOL_NAMES)}"), {
            "tool": name,
            "ok": False,
        }

    def _get_schema(self, payload: dict) -> tuple[str, dict]:
        table = payload.get("table")
        if table is not None and not isinstance(table, str):
            return _error("table має бути рядком"), {"tool": "get_schema", "ok": False}
        try:
            text = self.database.schema(table)
        except KeyError as exc:
            return _error(str(exc)), {"tool": "get_schema", "ok": False}
        return text, {"tool": "get_schema", "ok": True}

    def _run_sql(self, payload: dict) -> tuple[str, dict]:
        query = payload.get("query")
        if not isinstance(query, str):
            return _error("query має бути рядком"), {"tool": "run_sql", "ok": False}
        result = self.database.execute(query)
        return json.dumps(result, ensure_ascii=False, default=str), {
            "tool": "run_sql",
            "ok": bool(result["ok"]),
        }

    def _final_answer(self, payload: dict) -> tuple[str, dict]:
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return _error("text має бути непорожнім рядком"), {"tool": "final_answer", "ok": False}
        return json.dumps({"ok": True}, ensure_ascii=False), {
            "tool": "final_answer",
            "ok": True,
            "final_answer": text.strip(),
        }
