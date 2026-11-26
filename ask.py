#!/usr/bin/env python3
"""Одне питання до бази Chinook через агента."""
from __future__ import annotations

import argparse
import sys

from chinook_agent.calllog import CallLog
from chinook_agent.config import ConfigError, load_config
from chinook_agent.database import ReadOnlyDatabase
from chinook_agent.llm import LLMClient
from chinook_agent.loop import run_agent
from chinook_agent.tools import Toolbox


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--config")
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        database = ReadOnlyDatabase(cfg.database_path, cfg.sql.timeout_s, cfg.sql.max_rows)
    except ConfigError as exc:
        print(f"Конфіг: {exc}", file=sys.stderr)
        return 2

    call_log = CallLog(
        cfg.eval.results_dir / "ask_calls.jsonl",
        cfg.llm.price_per_1m_input,
        cfg.llm.price_per_1m_output,
    )
    result = run_agent(
        args.question,
        LLMClient(cfg.llm, call_log),
        Toolbox(database),
        args.max_steps or cfg.agent.max_steps,
    )

    if args.trace:
        for message in result.messages:
            role = message.get("role")
            content = message.get("content") or message.get("tool_calls") or ""
            print(f"--- {role} ---\n{content}\n", file=sys.stderr)

    if result.answer is None:
        reason = result.error or "вичерпано ліміт кроків"
        print(f"Відповіді немає: {reason}", file=sys.stderr)
        return 1

    print(result.answer)
    summary = call_log.summary()
    print(
        f"\nКроків: {result.steps}. Викликів інструментів: {result.tool_calls}. "
        f"Помилок SQL: {result.sql_errors}. Вартість: {summary['cost']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
