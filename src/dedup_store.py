import hashlib
import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .models import DedupConfig

logger = logging.getLogger(__name__)


class DedupStore:
    def __init__(self, config: DedupConfig):
        self.db_path = config.db_path
        self.url_ttl_days = config.url_ttl_days
        self.similarity_threshold = config.title_similarity_threshold
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_urls (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    source_name TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_titles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title_normalized TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_titles_created
                ON seen_titles(created_at)
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)

    def is_url_seen(self, url: str) -> bool:
        url_hash = self._hash_url(url)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_urls WHERE url_hash = ?", (url_hash,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE seen_urls SET last_seen_at = ? WHERE url_hash = ?",
                    (datetime.now(timezone.utc).isoformat(), url_hash),
                )
                return True
        return False

    def is_title_duplicate(self, title: str) -> bool:
        normalized = self._normalize_title(title)
        if not normalized:
            return False
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.url_ttl_days)
        ).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT title_normalized FROM seen_titles WHERE created_at > ?",
                (cutoff,),
            ).fetchall()
        for (existing,) in rows:
            ratio = SequenceMatcher(None, normalized, existing).ratio()
            if ratio >= self.similarity_threshold:
                return True
        return False

    def mark_seen(self, url: str, title: str, source_name: str):
        now = datetime.now(timezone.utc).isoformat()
        url_hash = self._hash_url(url)
        normalized_title = self._normalize_title(title)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO seen_urls
                   (url_hash, url, source_name, first_seen_at, last_seen_at)
                   VALUES (?, ?, ?, COALESCE(
                       (SELECT first_seen_at FROM seen_urls WHERE url_hash = ?), ?
                   ), ?)""",
                (url_hash, url, source_name, url_hash, now, now),
            )
            if normalized_title:
                conn.execute(
                    "INSERT INTO seen_titles (title_normalized, url, created_at) VALUES (?, ?, ?)",
                    (normalized_title, url, now),
                )

    def cleanup_expired(self):
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.url_ttl_days)
        ).isoformat()
        with self._connect() as conn:
            r1 = conn.execute(
                "DELETE FROM seen_urls WHERE last_seen_at < ?", (cutoff,)
            )
            r2 = conn.execute(
                "DELETE FROM seen_titles WHERE created_at < ?", (cutoff,)
            )
            logger.info(
                f"Dedup cleanup: removed {r1.rowcount} URLs, {r2.rowcount} titles"
            )

    def _hash_url(self, url: str) -> str:
        normalized = url.rstrip("/").lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _normalize_title(self, title: str) -> str:
        title = title.lower().strip()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title
