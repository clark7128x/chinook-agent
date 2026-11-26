import pytest

from chinook_agent.sqlguard import SqlRejected, check_select, ensure_limit, tokenize


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE Artist",
        "DELETE FROM Artist",
        "UPDATE Artist SET Name = 'x'",
        "INSERT INTO Artist VALUES (99, 'x')",
        "PRAGMA writable_schema = ON",
        "ATTACH DATABASE 'other.sqlite' AS other",
        "CREATE TABLE t(x)",
        "VACUUM",
    ],
)
def test_non_select_rejected(sql):
    with pytest.raises(SqlRejected):
        check_select(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1; DROP TABLE Artist",
        "SELECT 1;;",
    ],
)
def test_multiple_statements_rejected(sql):
    with pytest.raises(SqlRejected):
        check_select(sql)


def test_semicolon_inside_string_is_not_a_separator():
    tokens = check_select("SELECT * FROM Artist WHERE Name = 'a;b'")
    assert not any(token.kind == "semi" for token in tokens)


def test_comment_hides_injection_but_keeps_single_statement():
    check_select("SELECT 1 -- ; DROP TABLE Artist")


def test_unterminated_comment_and_quotes_rejected():
    with pytest.raises(SqlRejected):
        check_select("SELECT 1 /* немає кінця")
    with pytest.raises(SqlRejected):
        check_select("SELECT 'немає кінця")


@pytest.mark.parametrize("sql", ["", "   ", "-- лише коментар", None])
def test_empty_input_rejected(sql):
    with pytest.raises(SqlRejected):
        check_select(sql)


def test_limit_added_when_absent():
    prepared, added = ensure_limit("SELECT * FROM Artist", 100)
    assert added is True
    assert prepared.endswith("LIMIT 100")


def test_existing_limit_is_kept():
    prepared, added = ensure_limit("SELECT * FROM Artist LIMIT 5", 100)
    assert added is False
    assert prepared == "SELECT * FROM Artist LIMIT 5"


def test_limit_in_subquery_does_not_count():
    prepared, added = ensure_limit("SELECT * FROM (SELECT * FROM Album LIMIT 2)", 100)
    assert added is True
    assert prepared.endswith("LIMIT 100")


def test_trailing_semicolon_removed_before_limit():
    prepared, added = ensure_limit("SELECT 1;", 100)
    assert added is True
    assert prepared == "SELECT 1\nLIMIT 100"


def test_limit_appended_on_new_line_after_comment():
    prepared, added = ensure_limit("SELECT 1 -- кінець", 100)
    assert added is True
    assert prepared.splitlines()[-1] == "LIMIT 100"


def test_with_cte_allowed():
    check_select("WITH x AS (SELECT 1 AS a) SELECT a FROM x")


def test_recursive_cte_allowed():
    check_select("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c")


@pytest.mark.parametrize(
    "sql",
    [
        "WITH x AS (SELECT 1) DELETE FROM Artist",
        "WITH x AS (SELECT 1) INSERT INTO Artist VALUES (9, 'x')",
        "WITH x AS (SELECT 1) UPDATE Artist SET Name = 'x'",
        "WITH x AS (1) VALUES (2)",
    ],
)
def test_with_followed_by_non_select_rejected(sql):
    with pytest.raises(SqlRejected):
        check_select(sql)


def test_depth_tracking():
    tokens = tokenize("SELECT (SELECT 1) FROM t")
    inner = [token for token in tokens if token.kind == "number"]
    assert inner[0].depth == 1


def test_trailing_semicolon_with_comment_is_one_statement():
    prepared, added = ensure_limit("SELECT 1; -- коментар", 100)
    assert added is True
    assert prepared == "SELECT 1\nLIMIT 100"
