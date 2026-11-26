#!/usr/bin/env python3
"""Оцінка агента на задачах із data/tasks.jsonl."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from chinook_agent.calllog import CallLog
from chinook_agent.compare import CompareConfig, compare_answer
from chinook_agent.config import ConfigError, load_config
from chinook_agent.database import ReadOnlyDatabase
from chinook_agent.jsonio import read_jsonl, write_jsonl
from chinook_agent.llm import LLMClient
from chinook_agent.loop import run_agent
from chinook_agent.metrics import by_level, summarize
from chinook_agent.report import render_markdown
from chinook_agent.tools import Toolbox


def load_rows(path: Path, levels: tuple[str, ...]) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], [f"немає файлу {path}"]
    rows: list[dict] = []
    problems: list[str] = []
    for number, raw in enumerate(read_jsonl(path), start=1):
        task_id, level = raw.get("id"), raw.get("level")
        question, sql = raw.get("question"), raw.get("gold_sql")
        if not isinstance(task_id, str) or not task_id:
            problems.append(f"рядок {number}: немає id")
            continue
        if level not in levels:
            problems.append(f"рядок {number}: рівень {level!r} поза eval.levels")
            continue
        if not isinstance(question, str) or not question.strip():
            problems.append(f"рядок {number}: порожнє питання")
            continue
        if not isinstance(sql, str) or not sql.strip():
            problems.append(f"рядок {number}: немає gold_sql")
            continue
        rows.append({"id": task_id, "level": level, "question": question, "gold_sql": sql,
                     "stored_rows": raw.get("gold_rows")})
    return rows, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--levels", nargs="+")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        levels = tuple(args.levels) if args.levels else cfg.eval.levels
        database = ReadOnlyDatabase(cfg.database_path, cfg.sql.timeout_s, cfg.sql.max_rows)
        rows, problems = load_rows(cfg.eval.dataset, levels)
    except (ConfigError, ValueError) as exc:
        print(f"Вхідні дані: {exc}", file=sys.stderr)
        return 2

    for problem in problems:
        print(f"Пропущено: {problem}", file=sys.stderr)
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        print("Набір порожній. Запусти build_eval.py і повтори eval.py.", file=sys.stderr)
        return 2
    if not cfg.llm.configured:
        print("Не задано LLM_API_BASE або LLM_MODEL. Метрики не рахуються.", file=sys.stderr)
        return 2

    call_log = CallLog(cfg.eval.call_log, cfg.llm.price_per_1m_input, cfg.llm.price_per_1m_output)
    client = LLMClient(cfg.llm, call_log)
    toolbox = Toolbox(database)
    compare_cfg = CompareConfig(cfg.eval.value_abs_tol, cfg.eval.value_rel_tol)

    records: list[dict] = []
    details: list[dict] = []
    for row in rows:
        gold = database.execute(row["gold_sql"])
        if not gold["ok"]:
            problems.append(f"{row['id']}: еталонний запит не виконується: {gold['error']}")
            continue
        if row["stored_rows"] is not None and row["stored_rows"] != gold["rows"]:
            problems.append(f"{row['id']}: еталон змінився відносно збереженого в наборі")

        started = perf_counter()
        result = run_agent(row["question"], client, toolbox, cfg.agent.max_steps)
        elapsed = perf_counter() - started
        match = compare_answer(result.answer, gold["rows"], row["question"], compare_cfg)

        records.append(
            {
                "id": row["id"],
                "level": row["level"],
                "steps": result.steps,
                "tool_calls": result.tool_calls,
                "sql_calls": result.sql_calls,
                "sql_errors": result.sql_errors,
                "limit_reached": result.limit_reached,
                "error": result.error,
                "latency_s": elapsed,
                **{key: value for key, value in match.as_dict().items() if key != "missing"},
            }
        )
        details.append(
            {
                "id": row["id"],
                "level": row["level"],
                "question": row["question"],
                "gold_sql": gold["sql"],
                "gold_rows": gold["rows"],
                "answer": result.answer,
                "finished_via": result.finished_via,
                "match": match.as_dict(),
                "steps": result.steps,
                "tool_calls": result.tool_calls,
                "sql_errors": result.sql_errors,
                "limit_reached": result.limit_reached,
                "error": result.error,
                "messages": result.messages,
            }
        )

    if not records:
        print("Жодна задача не мала валідного еталону.", file=sys.stderr)
        return 2

    calls = call_log.summary()
    payload = {
        "run_id": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": cfg.llm.model,
        "config": {
            "max_steps": cfg.agent.max_steps,
            "max_rows": cfg.sql.max_rows,
            "sql_timeout_s": cfg.sql.timeout_s,
            "compare": {"abs_tol": compare_cfg.abs_tol, "rel_tol": compare_cfg.rel_tol},
        },
        "dataset": {"path": str(cfg.eval.dataset), "rows": len(records),
                    "skipped": len(problems), "problems": problems},
        "overall": summarize(records, calls["cost"]),
        "by_level": by_level(records, levels, calls["cost"]),
        "calls": calls,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = cfg.eval.results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = results_dir / f"eval_{stamp}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_jsonl(results_dir / f"details_{stamp}.jsonl", details)
    markdown = render_markdown(payload)
    (results_dir / "metrics.md").write_text(markdown, encoding="utf-8")

    print(markdown)
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
