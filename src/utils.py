import json
import logging
import logging.handlers
from datetime import date
from pathlib import Path

from .models import LoggingConfig


def setup_logging(config: LoggingConfig | None = None):
    if config is None:
        config = LoggingConfig()

    level = getattr(logging, config.level.upper(), logging.INFO)

    if config.format == "structured":
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    log_path = Path(config.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def get_output_dir(base_dir: str = "output") -> Path:
    today = date.today().isoformat()
    path = Path(base_dir) / today
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        if isinstance(data, list):
            serialized = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in data
            ]
        elif hasattr(data, "model_dump"):
            serialized = data.model_dump(mode="json")
        else:
            serialized = data
        json.dump(serialized, f, indent=2, ensure_ascii=False)


def save_markdown(content: str, filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
