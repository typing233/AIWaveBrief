from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .models import AppConfig, ArticleSummary, BriefSection, DailyBrief

CATEGORY_DISPLAY = {
    "research": "研究与论文",
    "industry": "行业动态",
    "news": "AI 资讯",
}

SOURCE_CATEGORY_MAP = {
    "arXiv": "research",
    "OpenAI": "industry",
    "Google AI": "industry",
    "Anthropic": "industry",
    "TechCrunch": "news",
    "The Verge": "news",
}


class BriefGenerator:
    def __init__(self, config: AppConfig):
        self.template_path = config.output.brief_template

    def generate(self, summaries: list[ArticleSummary], executive_summary: str) -> str:
        sections = self._group_by_category(summaries)
        brief = DailyBrief(
            date=date.today(),
            generated_at=datetime.now(timezone.utc),
            total_articles=len(summaries),
            sections=sections,
            executive_summary=executive_summary,
        )

        template_dir = str(Path(self.template_path).parent)
        template_file = Path(self.template_path).name
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template(template_file)

        return template.render(
            date=brief.date.isoformat(),
            generated_at=brief.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            total_articles=brief.total_articles,
            executive_summary=brief.executive_summary,
            sections=brief.sections,
        )

    def _group_by_category(
        self, summaries: list[ArticleSummary]
    ) -> list[BriefSection]:
        groups: dict[str, list[ArticleSummary]] = defaultdict(list)
        for s in summaries:
            category = self._infer_category(s.source_name)
            display_name = CATEGORY_DISPLAY.get(category, category)
            groups[display_name].append(s)

        ordered = []
        for display_name in CATEGORY_DISPLAY.values():
            if display_name in groups:
                articles = sorted(
                    groups[display_name],
                    key=lambda a: a.relevance_score or 0,
                    reverse=True,
                )
                ordered.append(BriefSection(category=display_name, articles=articles))

        for name, articles in groups.items():
            if name not in CATEGORY_DISPLAY.values():
                ordered.append(BriefSection(category=name, articles=articles))

        return ordered

    def _infer_category(self, source_name: str) -> str:
        for key, category in SOURCE_CATEGORY_MAP.items():
            if key.lower() in source_name.lower():
                return category
        return "news"
