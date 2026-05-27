from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


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
