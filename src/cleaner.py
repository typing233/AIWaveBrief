import hashlib
import re
from difflib import SequenceMatcher

from .models import ScrapedArticle

DATE_PATTERNS = [
    r"(\d{4}-\d{2}-\d{2})",
    r"(\w+ \d{1,2},?\s*\d{4})",
    r"(\d{1,2} \w+ \d{4})",
]

NAV_PATTERNS = [
    r"^(Skip to|Navigate to|Menu|Sign in|Subscribe|Newsletter|Cookie|Accept).*$",
    r"^\s*\|.*\|.*\|\s*$",
    r"^(Previous|Next|Back to|Related|Share|Follow us).*$",
]

TITLE_SIMILARITY_THRESHOLD = 0.85
CONTENT_SIMILARITY_THRESHOLD = 0.7


class ArticleCleaner:
    def clean(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        seen_urls: set[str] = set()
        seen_titles: list[str] = []
        seen_content_hashes: set[str] = set()
        cleaned = []

        for article in articles:
            # URL dedup (within this run)
            normalized_url = article.url.rstrip("/")
            if normalized_url in seen_urls:
                continue
            seen_urls.add(normalized_url)

            article.content_markdown = self._strip_boilerplate(
                article.content_markdown
            )
            if not article.published_date:
                article.published_date = self._extract_date(article.content_markdown)
            article.title = self._clean_title(article.title)

            if len(article.content_markdown.strip()) < 100:
                continue

            # Title similarity dedup (within this run)
            if self._is_title_duplicate(article.title, seen_titles):
                continue

            # Content fingerprint dedup (within this run)
            content_hash = self._content_fingerprint(article.content_markdown)
            if content_hash in seen_content_hashes:
                continue
            seen_content_hashes.add(content_hash)

            seen_titles.append(self._normalize_title(article.title))
            cleaned.append(article)

        return cleaned

    def _is_title_duplicate(self, title: str, seen_titles: list[str]) -> bool:
        normalized = self._normalize_title(title)
        if not normalized:
            return False
        for existing in seen_titles:
            if SequenceMatcher(None, normalized, existing).ratio() >= TITLE_SIMILARITY_THRESHOLD:
                return True
        return False

    def _normalize_title(self, title: str) -> str:
        title = title.lower().strip()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title

    def _content_fingerprint(self, markdown: str) -> str:
        text = re.sub(r"\s+", " ", markdown[:2000]).strip().lower()
        return hashlib.md5(text.encode()).hexdigest()

    def _strip_boilerplate(self, markdown: str) -> str:
        lines = markdown.split("\n")
        filtered = []
        for line in lines:
            if any(re.match(p, line.strip(), re.IGNORECASE) for p in NAV_PATTERNS):
                continue
            filtered.append(line)

        content = "\n".join(filtered)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    def _extract_date(self, text: str) -> str | None:
        search_area = text[:500]
        for pattern in DATE_PATTERNS:
            match = re.search(pattern, search_area)
            if match:
                return match.group(1)
        return None

    def _clean_title(self, title: str) -> str:
        title = re.sub(r"\s*[\|–—-]\s*[^|–—-]+$", "", title).strip()
        title = re.sub(r"\s+", " ", title)
        return title
