import logging
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from firecrawl import FirecrawlApp

from .models import ScrapedArticle, SourceConfig

logger = logging.getLogger(__name__)

ARTICLE_LINK_PATTERNS = {
    "research": [r"/abs/\d+\.\d+", r"/pdf/\d+\.\d+"],
    "industry": [r"/blog/", r"/news/", r"/research/", r"/posts/"],
    "news": [r"/\d{4}/\d{2}/\d{2}/", r"/article/", r"/news/"],
}


class ArticleScraper:
    def __init__(self, config: dict):
        self.client = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        scraping_cfg = config.get("scraping", {})
        self.max_retries = scraping_cfg.get("max_retries", 3)
        self.delay = scraping_cfg.get("request_delay_seconds", 2)
        self.max_articles_per_source = scraping_cfg.get("max_articles_per_source", 10)

    def scrape_source(self, source: SourceConfig) -> list[ScrapedArticle]:
        index_result = self._scrape_url(source.url)
        if not index_result:
            logger.warning(f"Failed to scrape index page for {source.name}")
            return []

        links = self._extract_article_links(index_result, source)
        logger.info(f"  Found {len(links)} article links from {source.name}")

        articles = []
        for link in links[: self.max_articles_per_source]:
            time.sleep(self.delay)
            result = self._scrape_url(link)
            if not result:
                continue
            markdown = result.get("markdown", "")
            metadata = result.get("metadata", {})
            title = metadata.get("title", "") or metadata.get("og:title", "") or ""
            if not title:
                title = self._extract_title_from_markdown(markdown)
            articles.append(
                ScrapedArticle(
                    source_name=source.name,
                    source_url=source.url,
                    title=title,
                    url=link,
                    published_date=metadata.get("publishedTime"),
                    content_markdown=markdown,
                    scraped_at=datetime.now(timezone.utc),
                )
            )
        return articles

    def _scrape_url(self, url: str) -> dict | None:
        for attempt in range(self.max_retries):
            try:
                result = self.client.scrape_url(url, params={"formats": ["markdown"]})
                return result
            except Exception as e:
                wait = 2**attempt
                logger.warning(
                    f"Scrape attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)
        logger.error(f"All scrape attempts failed for {url}")
        return None

    def _extract_article_links(
        self, index_result: dict, source: SourceConfig
    ) -> list[str]:
        markdown = index_result.get("markdown", "")
        raw_links = re.findall(r"\[([^\]]*)\]\((https?://[^\)]+)\)", markdown)
        if not raw_links:
            raw_links = re.findall(r"\[([^\]]*)\]\((/[^\)]+)\)", markdown)
            base = f"{urlparse(source.url).scheme}://{urlparse(source.url).netloc}"
            raw_links = [(text, urljoin(base, path)) for text, path in raw_links]

        patterns = ARTICLE_LINK_PATTERNS.get(source.category, [])
        source_domain = urlparse(source.url).netloc

        filtered = []
        seen = set()
        for text, url in raw_links:
            if url in seen:
                continue
            parsed = urlparse(url)
            if parsed.netloc and parsed.netloc != source_domain:
                continue
            if patterns:
                if any(re.search(p, url) for p in patterns):
                    filtered.append(url)
                    seen.add(url)
            else:
                if len(parsed.path.strip("/").split("/")) >= 2:
                    filtered.append(url)
                    seen.add(url)

        return filtered

    def _extract_title_from_markdown(self, markdown: str) -> str:
        match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
        if match:
            return match.group(1).strip()
        lines = markdown.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            if line and not line.startswith(("!", "[", "<", "---")):
                return line[:120]
        return "Untitled"
