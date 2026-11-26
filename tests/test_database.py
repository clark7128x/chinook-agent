import sqlite3

import pytest

from chinook_agent.config import ConfigError
from chinook_agent.database import ReadOnlyDatabase


def test_select_returns_rows_and_columns(database):
    result = database.execute("SELECT ArtistId, Name FROM Artist ORDER BY ArtistId")
    assert result["ok"] is True
    assert result["columns"] == ["ArtistId", "Name"]
    assert result["rows"] == [[1, "AC/DC"], [2, "Accept"]]
    assert result["limit_added"] is True


def test_drop_returns_error_not_exception(database):
    result = database.execute("DROP TABLE Artist")
    assert result["ok"] is False
    assert "лише SELECT" in result["error"]
    assert database.execute("SELECT COUNT(*) FROM Artist")["rows"] == [[2]]


def test_multiple_statements_return_error(database):
    result = database.execute("SELECT 1; DROP TABLE Artist")
    assert result["ok"] is False
    assert database.execute("SELECT COUNT(*) FROM Artist")["ok"] is True


def test_write_inside_cte_is_rejected(database):
    result = database.execute("WITH x AS (SELECT 1) INSERT INTO Artist VALUES (9, 'x')")
    assert result["ok"] is False
    assert database.execute("SELECT COUNT(*) FROM Artist")["rows"] == [[2]]


def test_authorizer_blocks_writes_even_if_text_check_is_bypassed(database):
    connection = database._connect()
    try:
        with pytest.raises(sqlite3.Error):
            connection.execute("INSERT INTO Artist VALUES (9, 'x')")
    finally:
        connection.close()
    assert database.execute("SELECT COUNT(*) FROM Artist")["rows"] == [[2]]


def test_syntax_error_returns_error(database):
    result = database.execute("SELECT FROM WHERE")
    assert result["ok"] is False
    assert "OperationalError" in result["error"]


def test_row_truncation_flag(mini_path):
    database = ReadOnlyDatabase(mini_path, timeout_s=1.0, max_rows=2)
    result = database.execute("SELECT AlbumId FROM Album ORDER BY AlbumId")
    assert result["row_count"] == 2
    assert result["truncated"] is True


def test_execution_timeout_interrupts(mini_path):
    database = ReadOnlyDatabase(mini_path, timeout_s=0.2, max_rows=10)
    result = database.execute(
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c"
    )
    assert result["ok"] is False
    assert "interrupt" in result["error"].lower()
    assert result["elapsed_s"] < 5


def test_missing_database_file(tmp_path):
    with pytest.raises(ConfigError):
        ReadOnlyDatabase(tmp_path / "absent.sqlite")


def test_connection_is_read_only(mini_path):
    database = ReadOnlyDatabase(mini_path)
    connection = database._connect()
    try:
        with pytest.raises(sqlite3.Error):
            connection.execute("INSERT INTO Artist VALUES (5, 'x')")
    finally:
        connection.close()


def test_schema_lists_tables_and_keys(database):
    text = database.schema()
    assert "Artist(ArtistId INTEGER" in text
    assert "FK: ArtistId -> Artist.ArtistId" in text
    assert "PK: AlbumId" in text


def test_schema_single_table_and_unknown(database):
    assert database.schema("Artist").startswith("Artist(")
    with pytest.raises(KeyError):
        database.schema("Nope")


def test_auto_limit_is_shown_as_max_rows_and_detects_truncation(mini_path):
    database = ReadOnlyDatabase(mini_path, timeout_s=1.0, max_rows=2)
    result = database.execute("SELECT AlbumId FROM Album ORDER BY AlbumId")
    assert result["sql"].endswith("LIMIT 2")
    assert result["rows"] == [[1], [2]] and result["truncated"] is True


def test_not_truncated_when_rows_fit(mini_path):
    database = ReadOnlyDatabase(mini_path, timeout_s=1.0, max_rows=3)
    result = database.execute("SELECT AlbumId FROM Album ORDER BY AlbumId")
    assert result["row_count"] == 3 and result["truncated"] is False


def test_model_limit_above_max_rows_is_trimmed(mini_path):
    database = ReadOnlyDatabase(mini_path, timeout_s=1.0, max_rows=2)
    result = database.execute("SELECT AlbumId FROM Album ORDER BY AlbumId LIMIT 50")
    assert result["row_count"] == 2 and result["truncated"] is True
