import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import HistoryConfig

logger = logging.getLogger(__name__)


class BriefHistory:
    def __init__(self, config: HistoryConfig):
        self.db_path = config.db_path
        self.keep_days = config.keep_days
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS briefs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    generated_at TEXT NOT NULL,
                    total_articles INTEGER,
                    file_path TEXT NOT NULL,
                    executive_summary TEXT,
                    sources_used TEXT,
                    push_status TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_briefs_date ON briefs(date)
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def record_brief(
        self,
        brief_date: str,
        file_path: str,
        total_articles: int,
        executive_summary: str,
        sources_used: list[str],
        push_status: dict[str, bool] | None = None,
    ):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO briefs
                   (date, generated_at, total_articles, file_path,
                    executive_summary, sources_used, push_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    brief_date,
                    now,
                    total_articles,
                    file_path,
                    executive_summary,
                    json.dumps(sources_used, ensure_ascii=False),
                    json.dumps(push_status or {}, ensure_ascii=False),
                ),
            )

    def list_briefs(self, limit: int = 30, offset: int = 0) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, generated_at, total_articles, file_path FROM briefs "
                "ORDER BY date DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_brief(self, brief_date: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM briefs WHERE date = ?", (brief_date,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        file_path = Path(result["file_path"])
        if file_path.exists():
            result["content"] = file_path.read_text(encoding="utf-8")
        return result

    def search(self, keyword: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, generated_at, total_articles, file_path "
                "FROM briefs WHERE executive_summary LIKE ? ORDER BY date DESC",
                (f"%{keyword}%",),
            ).fetchall()
        return [dict(row) for row in rows]

    def cleanup_old(self):
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self.keep_days)
        ).isoformat()[:10]
        with self._connect() as conn:
            result = conn.execute("DELETE FROM briefs WHERE date < ?", (cutoff,))
            if result.rowcount:
                logger.info(f"History cleanup: removed {result.rowcount} old briefs")

    def print_list(self, limit: int = 30):
        briefs = self.list_briefs(limit)
        if not briefs:
            print("暂无历史简报记录。")
            return
        print(f"\n{'日期':<12} {'文章数':<8} {'生成时间':<22} {'路径'}")
        print("-" * 70)
        for b in briefs:
            print(
                f"{b['date']:<12} {b['total_articles'] or 0:<8} "
                f"{b['generated_at'][:19]:<22} {b['file_path']}"
            )

    def print_brief(self, brief_date: str):
        brief = self.get_brief(brief_date)
        if not brief:
            print(f"未找到 {brief_date} 的简报。")
            return
        if "content" in brief:
            print(brief["content"])
        else:
            print(f"简报文件不存在: {brief['file_path']}")

    def print_search(self, keyword: str):
        results = self.search(keyword)
        if not results:
            print(f"未找到包含 '{keyword}' 的简报。")
            return
        print(f"\n搜索结果（关键词: '{keyword}'）:")
        print(f"{'日期':<12} {'文章数':<8} {'路径'}")
        print("-" * 50)
        for b in results:
            print(f"{b['date']:<12} {b['total_articles'] or 0:<8} {b['file_path']}")
