import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import RunStats

logger = logging.getLogger(__name__)


class HealthTracker:
    def __init__(self, db_path: str = "data/health.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_seconds REAL,
                    articles_scraped INTEGER,
                    articles_after_dedup INTEGER,
                    articles_after_clean INTEGER,
                    summaries_generated INTEGER,
                    push_results TEXT,
                    errors TEXT,
                    success INTEGER DEFAULT 1
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def record_run(self, stats: RunStats):
        success = 1 if not stats.errors else 0
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO run_history
                   (started_at, completed_at, duration_seconds,
                    articles_scraped, articles_after_dedup, articles_after_clean,
                    summaries_generated, push_results, errors, success)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stats.started_at.isoformat(),
                    stats.completed_at.isoformat() if stats.completed_at else None,
                    stats.duration_seconds,
                    stats.articles_scraped,
                    stats.articles_after_dedup,
                    stats.articles_after_clean,
                    stats.summaries_generated,
                    json.dumps(stats.push_results, ensure_ascii=False),
                    json.dumps(stats.errors, ensure_ascii=False),
                    success,
                ),
            )

    def get_stats(self, days: int = 7) -> dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_history WHERE started_at > ? ORDER BY started_at DESC",
                (cutoff,),
            ).fetchall()

        if not rows:
            return {"total_runs": 0, "period_days": days}

        total = len(rows)
        successful = sum(1 for r in rows if r["success"])
        total_articles = sum(r["articles_scraped"] or 0 for r in rows)
        avg_duration = sum(r["duration_seconds"] or 0 for r in rows) / total
        errors = []
        for r in rows:
            if r["errors"]:
                errors.extend(json.loads(r["errors"]))

        return {
            "period_days": days,
            "total_runs": total,
            "successful_runs": successful,
            "failed_runs": total - successful,
            "success_rate": f"{successful/total*100:.1f}%",
            "total_articles_scraped": total_articles,
            "avg_duration_seconds": round(avg_duration, 1),
            "last_run": rows[0]["started_at"],
            "recent_errors": errors[:10],
        }

    def print_health(self, next_run: str | None = None):
        stats = self.get_stats()
        print("\n=== AIWaveBrief 运行状态 ===\n")

        if stats["total_runs"] == 0:
            print("暂无运行记录。")
            return

        print(f"统计周期:       最近 {stats['period_days']} 天")
        print(f"总运行次数:     {stats['total_runs']}")
        print(f"成功次数:       {stats['successful_runs']}")
        print(f"失败次数:       {stats['failed_runs']}")
        print(f"成功率:         {stats['success_rate']}")
        print(f"抓取文章总数:   {stats['total_articles_scraped']}")
        print(f"平均耗时:       {stats['avg_duration_seconds']}s")
        print(f"最后运行:       {stats['last_run']}")

        if next_run:
            print(f"下次调度:       {next_run}")

        if stats.get("recent_errors"):
            print(f"\n最近错误 (共 {len(stats['recent_errors'])} 条):")
            for err in stats["recent_errors"][:5]:
                print(f"  - {err}")
