import json
import logging
import os

from openai import OpenAI

from .models import ArticleSummary, ScrapedArticle

logger = logging.getLogger(__name__)

ARTICLE_SUMMARY_PROMPT = """你是一位 AI 领域资讯分析师。给定一篇文章，请输出一个 JSON 对象，格式如下：
{
  "key_points": ["要点1", "要点2", "要点3"],
  "one_line_summary": "一句话总结",
  "relevance_score": 0.85
}

要求：
- key_points: 3-5 个要点，聚焦新颖性和重要性
- one_line_summary: 一句话概括核心内容
- relevance_score: 0.0-1.0，衡量对 AI 从业者的重要程度
- 使用中文输出"""

EXECUTIVE_SUMMARY_PROMPT = """你是一位 AI 资讯编辑，正在撰写每日简报的总结。
根据今日所有文章摘要，撰写 2-3 段综述，涵盖：
1. 最重要的发展动态
2. 共同主题或趋势
3. AI 从业者需要关注的方向

要求：语言专业但易读，使用中文输出。"""


class Summarizer:
    def __init__(self, config: dict):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        summarization_cfg = config.get("summarization", {})
        self.model = summarization_cfg.get("model", "gpt-4o")
        self.max_tokens = summarization_cfg.get("max_tokens_per_summary", 500)
        self.max_tokens_brief = summarization_cfg.get("max_tokens_brief", 4000)
        self.temperature = summarization_cfg.get("temperature", 0.3)
        self.content_max_chars = summarization_cfg.get("content_max_chars", 6000)

    def summarize_article(self, article: ScrapedArticle) -> ArticleSummary:
        content = article.content_markdown[: self.content_max_chars]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": ARTICLE_SUMMARY_PROMPT},
                    {
                        "role": "user",
                        "content": f"标题: {article.title}\n来源: {article.source_name}\n\n正文:\n{content}",
                    },
                ],
            )
            data = json.loads(response.choices[0].message.content)
            return ArticleSummary(
                source_name=article.source_name,
                title=article.title,
                url=article.url,
                key_points=data.get("key_points", []),
                one_line_summary=data.get("one_line_summary", ""),
                relevance_score=data.get("relevance_score"),
            )
        except Exception as e:
            logger.error(f"Failed to summarize '{article.title}': {e}")
            return ArticleSummary(
                source_name=article.source_name,
                title=article.title,
                url=article.url,
                key_points=["Summarization failed"],
                one_line_summary="Unable to generate summary",
                relevance_score=0.0,
            )

    def generate_executive_summary(self, summaries: list[ArticleSummary]) -> str:
        summaries_text = "\n".join(
            f"- 【{s.source_name}】{s.title}: {s.one_line_summary}"
            for s in summaries
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens_brief,
                messages=[
                    {"role": "system", "content": EXECUTIVE_SUMMARY_PROMPT},
                    {"role": "user", "content": summaries_text},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return "Executive summary generation failed."
