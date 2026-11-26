from pathlib import Path

import pytest

from chinook_agent.config import load_config
from chinook_agent.database import ReadOnlyDatabase
from chinook_agent.tasks import LEVEL_SIZES, TASK_COUNT, TaskError, build_tasks, one, quote, rows

CHINOOK = Path("data/Chinook_Sqlite.sqlite")
needs_chinook = pytest.mark.skipif(not CHINOOK.is_file(), reason="немає data/Chinook_Sqlite.sqlite")


def test_quote_escapes_apostrophe():
    assert quote("O'Brien") == "'O''Brien'"
    assert quote(7) == "7"


def test_rows_raises_on_bad_sql(database):
    with pytest.raises(TaskError):
        rows(database, "DELETE FROM Artist")


def test_one_raises_on_empty_result(database):
    with pytest.raises(TaskError):
        one(database, "SELECT Name FROM Artist WHERE ArtistId = 999")


def test_level_sizes_sum_to_task_count():
    assert sum(LEVEL_SIZES.values()) == TASK_COUNT


@needs_chinook
def test_catalog_builds_fifty_tasks_with_gold():
    cfg = load_config(env={})
    database = ReadOnlyDatabase(cfg.database_path, cfg.sql.timeout_s, cfg.sql.max_rows)
    tasks = build_tasks(database, seed=17)
    assert len(tasks) == TASK_COUNT
    assert {task["level"] for task in tasks} == set(LEVEL_SIZES)
    for task in tasks:
        assert task["gold_rows"] and task["gold_sql"].strip().upper().startswith(("SELECT", "WITH"))
        assert all(cell is not None for row in task["gold_rows"] for cell in row)


@needs_chinook
def test_catalog_is_deterministic():
    cfg = load_config(env={})
    database = ReadOnlyDatabase(cfg.database_path, cfg.sql.timeout_s, cfg.sql.max_rows)
    assert build_tasks(database, 17) == build_tasks(database, 17)
