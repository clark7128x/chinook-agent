import pytest

from chinook_agent.config import ConfigError, load_config

MINIMAL = """
database:
  path: data/Chinook_Sqlite.sqlite
agent:
  max_steps: 8
"""


def write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_and_relative_paths(tmp_path):
    cfg = load_config(write(tmp_path, MINIMAL), env={})
    assert cfg.sql.max_rows == 100
    assert cfg.agent.max_steps == 8
    assert cfg.database_path == (tmp_path / "data/Chinook_Sqlite.sqlite").resolve()
    assert cfg.eval.dataset == (tmp_path / "data/tasks.jsonl").resolve()


def test_env_overrides(tmp_path):
    cfg = load_config(
        write(tmp_path, MINIMAL),
        env={"CHINOOK_DB": "/tmp/other.sqlite", "LLM_API_BASE": "http://x/v1",
             "LLM_API_KEY": "k", "LLM_MODEL": "m"},
    )
    assert cfg.database_path.as_posix() == "/tmp/other.sqlite"
    assert cfg.llm.configured is True and cfg.llm.api_key == "k"


def test_llm_unconfigured_by_default(tmp_path):
    assert load_config(write(tmp_path, MINIMAL), env={}).llm.configured is False


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.yaml", env={})


@pytest.mark.parametrize(
    "text",
    [
        "agent:\n  max_steps: 0\n",
        "sql:\n  max_rows: 0\n",
        "sql:\n  timeout_s: 0\n",
        "sql:\n  unknown: 1\n",
        "eval:\n  levels: [hard]\n",
        "eval:\n  value_abs_tol: -1\n",
        "llm:\n  price_per_1m_input: -1\n",
    ],
)
def test_invalid_configs(tmp_path, text):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, text), env={})
