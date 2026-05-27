from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class SourceConfig(BaseModel):
    name: str
    url: str
    category: str
    enabled: bool = True


class ScrapedArticle(BaseModel):
    source_name: str
    source_url: str
    title: str
    url: str
    published_date: Optional[str] = None
    content_markdown: str
    scraped_at: datetime


class ArticleSummary(BaseModel):
    source_name: str
    title: str
    url: str
    key_points: list[str]
    one_line_summary: str
    relevance_score: Optional[float] = None


class BriefSection(BaseModel):
    category: str
    articles: list[ArticleSummary]


class DailyBrief(BaseModel):
    date: date
    generated_at: datetime
    total_articles: int
    sections: list[BriefSection]
    executive_summary: str


# --- New configuration models ---


class ScrapingConfig(BaseModel):
    max_retries: int = 3
    retry_delay_seconds: float = 5
    request_delay_seconds: float = 2
    max_articles_per_source: int = 10
    max_workers: int = 3


class SummarizationConfig(BaseModel):
    model: str = "gpt-4o"
    max_tokens_per_summary: int = 500
    max_tokens_brief: int = 4000
    temperature: float = 0.3
    content_max_chars: int = 6000


class OutputConfig(BaseModel):
    base_dir: str = "output"
    brief_template: str = "templates/brief_template.md"


class ScheduleConfig(BaseModel):
    enabled: bool = True
    time: str = "08:00"
    timezone: str = "Asia/Shanghai"


class DedupConfig(BaseModel):
    enabled: bool = True
    db_path: str = "data/dedup.db"
    url_ttl_days: int = 30
    title_similarity_threshold: float = 0.85


class PushChannelConfig(BaseModel):
    type: str = "email"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_ssl: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = []
    url: str = ""
    headers: dict[str, str] = {}


class PushConfig(BaseModel):
    enabled: bool = False
    channels: list[PushChannelConfig] = []


class HistoryConfig(BaseModel):
    enabled: bool = True
    db_path: str = "data/history.db"
    keep_days: int = 90


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "structured"
    file: str = "data/aiwavebrief.log"


class AppConfig(BaseModel):
    scraping: ScrapingConfig = ScrapingConfig()
    summarization: SummarizationConfig = SummarizationConfig()
    output: OutputConfig = OutputConfig()
    sources: list[SourceConfig] = []
    schedule: ScheduleConfig = ScheduleConfig()
    dedup: DedupConfig = DedupConfig()
    push: PushConfig = PushConfig()
    history: HistoryConfig = HistoryConfig()
    logging: LoggingConfig = LoggingConfig()


class RunStats(BaseModel):
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0
    articles_scraped: int = 0
    articles_after_dedup: int = 0
    articles_after_clean: int = 0
    summaries_generated: int = 0
    push_results: dict[str, bool] = {}
    errors: list[str] = []
