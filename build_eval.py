#!/usr/bin/env python3
"""Створює 50 задач трьох рівнів і рахує еталони виконанням SQL у базі."""
from __future__ import annotations

import argparse
import sys

from chinook_agent.config import ConfigError, load_config
from chinook_agent.database import ReadOnlyDatabase
from chinook_agent.jsonio import write_jsonl
from chinook_agent.tasks import TaskError, build_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out")
    args = parser.parse_args()

    try:
        cfg = load_config(args.config)
        database = ReadOnlyDatabase(cfg.database_path, cfg.sql.timeout_s, cfg.sql.max_rows)
        tasks = build_tasks(database, args.seed if args.seed is not None else cfg.build.seed)
    except (ConfigError, TaskError) as exc:
        print(f"Побудова набору: {exc}", file=sys.stderr)
        return 2

    out = args.out or cfg.eval.dataset
    write_jsonl(out, tasks)
    counts = {level: sum(1 for task in tasks if task["level"] == level) for level in cfg.eval.levels}
    print(f"Записано {len(tasks)} задач у {out}")
    print(f"За рівнями: {counts}")
    print("Еталони обчислені виконанням gold_sql у базі, модель не використовувалась.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
