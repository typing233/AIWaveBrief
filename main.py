"""AIWaveBrief — AI 资讯日报自动生成工具"""

import logging

from src.brief_generator import BriefGenerator
from src.cleaner import ArticleCleaner
from src.config_loader import load_config, load_env
from src.scraper import ArticleScraper
from src.summarizer import Summarizer
from src.utils import get_output_dir, save_json, save_markdown, setup_logging


def main():
    setup_logging()
    logger = logging.getLogger("AIWaveBrief")

    logger.info("=== AIWaveBrief 启动 ===")

    # 1. 加载配置
    logger.info("加载配置...")
    load_env()
    config = load_config()

    # 2. 抓取内容
    logger.info("开始抓取信息源...")
    scraper = ArticleScraper(config)
    all_articles = []
    sources = [s for s in config["sources"] if s.enabled]
    for source in sources:
        logger.info(f"  抓取: {source.name} ({source.url})")
        articles = scraper.scrape_source(source)
        all_articles.extend(articles)
        logger.info(f"    获取 {len(articles)} 篇文章")

    if not all_articles:
        logger.warning("未抓取到任何文章，流程终止。")
        return

    # 3. 清洗去重
    logger.info("清洗和去重...")
    cleaner = ArticleCleaner()
    cleaned = cleaner.clean(all_articles)
    logger.info(f"  清洗后保留 {len(cleaned)} 篇文章")

    # 4. 保存原始数据
    output_dir = get_output_dir(config.get("output", {}).get("base_dir", "output"))
    save_json(cleaned, output_dir / "raw.json")
    logger.info(f"  原始数据已保存: {output_dir / 'raw.json'}")

    # 5. 摘要生成
    logger.info("生成文章摘要...")
    summarizer = Summarizer(config)
    summaries = []
    for i, article in enumerate(cleaned, 1):
        logger.info(f"  [{i}/{len(cleaned)}] {article.title[:50]}...")
        summary = summarizer.summarize_article(article)
        summaries.append(summary)
    save_json(summaries, output_dir / "summaries.json")
    logger.info(f"  摘要已保存: {output_dir / 'summaries.json'}")

    # 6. 生成综述
    logger.info("生成今日综述...")
    exec_summary = summarizer.generate_executive_summary(summaries)

    # 7. 渲染日报
    logger.info("渲染每日简报...")
    generator = BriefGenerator(config)
    brief_md = generator.generate(summaries, exec_summary)
    save_markdown(brief_md, output_dir / "brief.md")

    logger.info("=== 完成 ===")
    logger.info(f"  日报路径: {output_dir / 'brief.md'}")
    logger.info(f"  文章总数: {len(cleaned)}")
    logger.info(f"  摘要总数: {len(summaries)}")


if __name__ == "__main__":
    main()
