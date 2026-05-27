import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import SourceConfig


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    raw["sources"] = [SourceConfig(**s) for s in raw.get("sources", [])]
    return raw


def load_env():
    load_dotenv()
    required = ["FIRECRAWL_API_KEY", "OPENAI_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in your API keys."
        )
