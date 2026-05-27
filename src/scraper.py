import logging
import os
import random
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from firecrawl import FirecrawlApp

from .models import AppConfig, ScrapedArticle, SourceConfig
from .dedup_store import DedupStore

logger = logging.getLogger(__name__)

ARTICLE_LINK_PATTERNS = {
    "research": [r"/abs/\d+\.\d+", r"/pdf/\d+\.\d+"],
    "industry": [r"/blog/", r"/news/", r"/research/", r"/posts/"],
    "news": [r"/\d{4}/\d{2}/\d{2}/", r"/article/", r"/news/"],
}

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ArticleScraper:
    def __init__(self, config: AppConfig, dedup_store: DedupStore | None = None):
        self.client = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        self.max_retries = config.scraping.max_retries
        self.delay = config.scraping.request_delay_seconds
        self.max_articles_per_source = config.scraping.max_articles_per_source
        self.max_workers = config.scraping.max_workers
        self.dedup_store = dedup_store
        self._domain_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._domain_last_request: dict[str, float] = {}

    def scrape_all_sources(self, sources: list[SourceConfig]) -> list[ScrapedArticle]:
        all_articles = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.scrape_source, source): source
                for source in sources
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    articles = future.result()
                    all_articles.extend(articles)
                    logger.info(f"  {source.name}: 获取 {len(articles)} 篇文章")
                except Exception as e:
                    logger.error(f"  {source.name} 抓取失败: {e}")
        return all_articles

    def scrape_source(self, source: SourceConfig) -> list[ScrapedArticle]:
        index_doc = self._scrape_url(source.url)
        if not index_doc:
            logger.warning(f"Failed to scrape index page for {source.name}")
            return []

        links = self._extract_article_links(index_doc, source)
        logger.info(f"  Found {len(links)} article links from {source.name}")

        # Pre-filter: skip URLs already in dedup store
        if self.dedup_store:
            before = len(links)
            links = [url for url in links if not self.dedup_store.is_url_seen(url)]
            skipped = before - len(links)
            if skipped:
                logger.info(f"  跳过 {skipped} 个已抓取 URL ({source.name})")

        articles = []
        for link in links[: self.max_articles_per_source]:
            self._rate_limit(link)
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

    def _rate_limit(self, url: str):
        domain = urlparse(url).netloc
        with self._domain_locks[domain]:
            last = self._domain_last_request.get(domain, 0)
            elapsed = time.time() - last
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self._domain_last_request[domain] = time.time()

    def _scrape_url(self, url: str):
        for attempt in range(self.max_retries):
            try:
                self._rate_limit(url)
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
                error_msg = str(e)
                if "404" in error_msg or "403" in error_msg:
                    logger.warning(f"Permanent error for {url}: {e}")
                    return None
                wait = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Scrape attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}. "
                    f"Retrying in {wait:.1f}s..."
                )
                time.sleep(wait)
        logger.error(f"All scrape attempts failed for {url}")
        return None

    def _extract_article_links(self, doc, source: SourceConfig) -> list[str]:
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
