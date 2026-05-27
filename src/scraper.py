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
        index_doc = self._scrape_url(source.url)
        if not index_doc:
            logger.warning(f"Failed to scrape index page for {source.name}")
            return []

        links = self._extract_article_links(index_doc, source)
        logger.info(f"  Found {len(links)} article links from {source.name}")

        articles = []
        for link in links[: self.max_articles_per_source]:
            time.sleep(self.delay)
            doc = self._scrape_url(link)
            if not doc:
                continue

            markdown = doc.markdown or ""
            metadata = doc.metadata or {}
            if hasattr(metadata, "model_dump"):
                metadata = metadata.model_dump(exclude_none=True)

            title = (
                metadata.get("title")
                or metadata.get("og_title")
                or metadata.get("ogTitle")
                or ""
            )
            if not title:
                title = self._extract_title_from_markdown(markdown)

            published_date = (
                metadata.get("published_time")
                or metadata.get("publishedTime")
                or metadata.get("modified_time")
                or metadata.get("modifiedTime")
            )

            articles.append(
                ScrapedArticle(
                    source_name=source.name,
                    source_url=source.url,
                    title=title,
                    url=metadata.get("source_url") or metadata.get("sourceURL") or link,
                    published_date=published_date,
                    content_markdown=markdown,
                    scraped_at=datetime.now(timezone.utc),
                )
            )
        return articles

    def _scrape_url(self, url: str):
        """Scrape a single URL via Firecrawl v2 API. Returns a Document or None."""
        for attempt in range(self.max_retries):
            try:
                doc = self.client.scrape_url(
                    url,
                    formats=["markdown"],
                    only_main_content=True,
                    timeout=30000,
                )
                if doc and (doc.markdown or "").strip():
                    return doc
                logger.warning(f"Empty content returned for {url}")
                return None
            except Exception as e:
                wait = 2**attempt
                logger.warning(
                    f"Scrape attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)
        logger.error(f"All scrape attempts failed for {url}")
        return None

    def _extract_article_links(self, doc, source: SourceConfig) -> list[str]:
        """Extract article URLs from an index page Document."""
        markdown = doc.markdown or ""

        raw_links = re.findall(r"\[([^\]]*)\]\((https?://[^\)]+)\)", markdown)

        base = f"{urlparse(source.url).scheme}://{urlparse(source.url).netloc}"
        relative_links = re.findall(r"\[([^\]]*)\]\((/[^\)]+)\)", markdown)
        raw_links += [(text, urljoin(base, path)) for text, path in relative_links]

        if doc.links:
            for link in doc.links:
                if link.startswith("http"):
                    raw_links.append(("", link))
                elif link.startswith("/"):
                    raw_links.append(("", urljoin(base, link)))

        patterns = ARTICLE_LINK_PATTERNS.get(source.category, [])
        source_domain = urlparse(source.url).netloc

        filtered = []
        seen = set()
        for _text, url in raw_links:
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
