import re

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


class ArticleCleaner:
    def clean(self, articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        seen_urls = set()
        cleaned = []
        for article in articles:
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

            if len(article.content_markdown.strip()) > 100:
                cleaned.append(article)

        return cleaned

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
