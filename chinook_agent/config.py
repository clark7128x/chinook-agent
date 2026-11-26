from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Mapping

import yaml

LEVELS = ("single", "join", "aggregate")


class ConfigError(ValueError):
    pass


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise ConfigError(msg)


def _build(cls, data: dict, section: str):
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    _need(not unknown, f"{section}: невідомі ключі {sorted(unknown)}")
    try:
        return cls(**data)
    except TypeError as exc:
        raise ConfigError(f"{section}: {exc}") from exc


@dataclass(frozen=True)
class SqlConfig:
    max_rows: int = 100
    timeout_s: float = 5.0

    def __post_init__(self) -> None:
        _need(self.max_rows > 0, "sql.max_rows має бути > 0")
        _need(self.timeout_s > 0, "sql.timeout_s має бути > 0")


@dataclass(frozen=True)
class AgentConfig:
    max_steps: int = 8

    def __post_init__(self) -> None:
        _need(self.max_steps > 0, "agent.max_steps має бути > 0")


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = ""
    api_key: str | None = None
    model: str | None = None
    temperature: float = 0.0
    max_output_tokens: int = 800
    timeout_s: float = 60.0
    max_retries: int = 3
    retry_base_delay_s: float = 1.0
    retry_max_delay_s: float = 20.0
    price_per_1m_input: float | None = None
    price_per_1m_output: float | None = None

    def __post_init__(self) -> None:
        _need(self.temperature >= 0, "llm.temperature має бути >= 0")
        _need(self.max_output_tokens > 0, "llm.max_output_tokens має бути > 0")
        _need(self.timeout_s > 0, "llm.timeout_s має бути > 0")
        _need(self.max_retries >= 0, "llm.max_retries має бути >= 0")
        for name in ("price_per_1m_input", "price_per_1m_output"):
            value = getattr(self, name)
            _need(value is None or value >= 0, f"llm.{name} має бути >= 0 або null")

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)


@dataclass(frozen=True)
class BuildConfig:
    seed: int = 17


@dataclass(frozen=True)
class EvalConfig:
    dataset: Path
    levels: tuple[str, ...] = LEVELS
    results_dir: Path = Path("results")
    call_log: Path = Path("results/calls.jsonl")
    value_abs_tol: float = 0.005
    value_rel_tol: float = 1e-6

    def __post_init__(self) -> None:
        _need(self.value_abs_tol >= 0, "eval.value_abs_tol має бути >= 0")
        _need(self.value_rel_tol >= 0, "eval.value_rel_tol має бути >= 0")
        _need(bool(self.levels), "eval.levels не може бути порожнім")
        _need(all(level in LEVELS for level in self.levels), f"eval.levels має бути з {LEVELS}")


@dataclass(frozen=True)
class Config:
    database_path: Path
    sql: SqlConfig
    agent: AgentConfig
    llm: LLMConfig
    build: BuildConfig
    eval: EvalConfig
    raw: dict[str, Any]


def load_config(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    cfg_path = Path(path or env.get("CHINOOK_CONFIG") or "config.yaml")
    if not cfg_path.is_file():
        raise ConfigError(f"Немає конфігу: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    _need(isinstance(raw, dict), "config.yaml має містити словник")
    base = cfg_path.resolve().parent

    def resolve(value: str | Path) -> Path:
        return (base / value).resolve()

    database = dict(raw.get("database") or {})
    db_path = env.get("CHINOOK_DB") or database.get("path", "data/Chinook_Sqlite.sqlite")

    llm_raw = dict(raw.get("llm") or {})
    llm_raw["base_url"] = env.get("LLM_API_BASE") or llm_raw.get("base_url") or ""
    llm_raw["api_key"] = env.get("LLM_API_KEY") or None
    llm_raw["model"] = env.get("LLM_MODEL") or llm_raw.get("model") or None

    eval_raw = dict(raw.get("eval") or {})
    eval_section = _build(
        EvalConfig,
        eval_raw | {"dataset": resolve(eval_raw.get("dataset", "data/tasks.jsonl"))},
        "eval",
    )
    eval_cfg = EvalConfig(
        dataset=eval_section.dataset,
        levels=tuple(eval_section.levels),
        results_dir=resolve(eval_raw.get("results_dir", "results")),
        call_log=resolve(eval_raw.get("call_log", "results/calls.jsonl")),
        value_abs_tol=eval_section.value_abs_tol,
        value_rel_tol=eval_section.value_rel_tol,
    )

    return Config(
        database_path=resolve(db_path),
        sql=_build(SqlConfig, raw.get("sql") or {}, "sql"),
        agent=_build(AgentConfig, raw.get("agent") or {}, "agent"),
        llm=_build(LLMConfig, llm_raw, "llm"),
        build=_build(BuildConfig, raw.get("build") or {}, "build"),
        eval=eval_cfg,
        raw=raw,
    )
