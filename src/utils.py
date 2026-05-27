import json
import logging
from datetime import date
from pathlib import Path


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def get_output_dir(base_dir: str = "output") -> Path:
    today = date.today().isoformat()
    path = Path(base_dir) / today
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data, filepath: Path):
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
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
