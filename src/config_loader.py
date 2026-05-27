import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import (
    AppConfig,
    DedupConfig,
    HistoryConfig,
    LoggingConfig,
    OutputConfig,
    PushChannelConfig,
    PushConfig,
    ScheduleConfig,
    ScrapingConfig,
    SourceConfig,
    SummarizationConfig,
)

ENV_PREFIX = "AIWAVEBRIEF_"


def load_env():
    load_dotenv()
    required = ["FIRECRAWL_API_KEY", "OPENAI_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in your API keys."
        )


def load_config(config_path: str = "config.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    raw = _apply_env_overrides(raw)

    sources = [SourceConfig(**s) for s in raw.get("sources", [])]
    sources_json = os.getenv(f"{ENV_PREFIX}SOURCES_JSON")
    if sources_json:
        sources = [SourceConfig(**s) for s in json.loads(sources_json)]

    return AppConfig(
        scraping=ScrapingConfig(**raw.get("scraping", {})),
        summarization=SummarizationConfig(**raw.get("summarization", {})),
        output=OutputConfig(**raw.get("output", {})),
        sources=sources,
        schedule=ScheduleConfig(**raw.get("schedule", {})),
        dedup=DedupConfig(**raw.get("dedup", {})),
        push=_build_push_config(raw.get("push", {})),
        history=HistoryConfig(**raw.get("history", {})),
        logging=LoggingConfig(**raw.get("logging", {})),
    )


def _build_push_config(raw_push: dict) -> PushConfig:
    channels = []
    for ch in raw_push.get("channels", []):
        channels.append(PushChannelConfig(**ch))
    return PushConfig(
        enabled=raw_push.get("enabled", False),
        channels=channels,
    )


def _apply_env_overrides(raw: dict) -> dict:
    """Override config values from AIWAVEBRIEF_<SECTION>_<KEY> env vars."""
    for key, value in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        parts = key[len(ENV_PREFIX) :].lower().split("_", 1)
        if len(parts) != 2:
            continue
        section, field = parts
        if section not in raw:
            raw[section] = {}
        if isinstance(raw[section], dict):
            raw[section][field] = _parse_env_value(value)
    return raw


def _parse_env_value(value: str):
    """Try to parse as JSON for booleans/numbers/lists, fallback to string."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value
