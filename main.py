"""AIWaveBrief — AI 资讯日报自动生成工具"""

import argparse
import logging
from datetime import date, datetime, timezone

from src.brief_generator import BriefGenerator
from src.cleaner import ArticleCleaner
from src.config_loader import load_config, load_env
from src.dedup_store import DedupStore
from src.health import HealthTracker
from src.history import BriefHistory
from src.models import AppConfig, RunStats
from src.push import create_push_adapters, push_brief
from src.scraper import ArticleScraper
from src.summarizer import Summarizer
from src.utils import get_output_dir, save_json, save_markdown, setup_logging


def run_pipeline(config: AppConfig) -> RunStats:
    logger = logging.getLogger("AIWaveBrief")
    stats = RunStats(started_at=datetime.now(timezone.utc))
    errors: list[str] = []

    try:
        logger.info("=== AIWaveBrief 启动 ===")

        # 1. Dedup store
        dedup = None
        if config.dedup.enabled:
            dedup = DedupStore(config.dedup)
            dedup.cleanup_expired()

        # 2. Scrape
        logger.info("开始抓取信息源...")
        scraper = ArticleScraper(config)
        sources = [s for s in config.sources if s.enabled]
        all_articles = scraper.scrape_all_sources(sources)
        stats.articles_scraped = len(all_articles)
        logger.info(f"  共抓取 {len(all_articles)} 篇文章")

        if not all_articles:
            logger.warning("未抓取到任何文章，流程终止。")
            errors.append("未抓取到任何文章")
            stats.errors = errors
            return stats

        # 3. Cross-run dedup
        if dedup:
            before = len(all_articles)
            all_articles = [
                a
                for a in all_articles
                if not dedup.is_url_seen(a.url)
                and not dedup.is_title_duplicate(a.title)
            ]
            stats.articles_after_dedup = len(all_articles)
            logger.info(f"  跨次去重: {before} -> {len(all_articles)} 篇")
            if not all_articles:
                logger.info("所有文章均已处理过，无新内容。")
                stats.errors = errors
                return stats
        else:
            stats.articles_after_dedup = len(all_articles)

        # 4. Clean
        logger.info("清洗和去重...")
        cleaner = ArticleCleaner()
        cleaned = cleaner.clean(all_articles)
        stats.articles_after_clean = len(cleaned)
        logger.info(f"  清洗后保留 {len(cleaned)} 篇文章")

        if not cleaned:
            logger.warning("清洗后无有效文章。")
            errors.append("清洗后无有效文章")
            stats.errors = errors
            return stats

        # 5. Save raw
        output_dir = get_output_dir(config.output.base_dir)
        save_json(cleaned, output_dir / "raw.json")

        # 6. Summarize
        logger.info("生成文章摘要...")
        summarizer = Summarizer(config)
        summaries = []
        for i, article in enumerate(cleaned, 1):
            logger.info(f"  [{i}/{len(cleaned)}] {article.title[:50]}...")
            summary = summarizer.summarize_article(article)
            summaries.append(summary)
        stats.summaries_generated = len(summaries)
        save_json(summaries, output_dir / "summaries.json")

        # 7. Executive summary
        logger.info("生成今日综述...")
        exec_summary = summarizer.generate_executive_summary(summaries)

        # 8. Render brief
        logger.info("渲染每日简报...")
        generator = BriefGenerator(config)
        brief_md = generator.generate(summaries, exec_summary)
        brief_path = output_dir / "brief.md"
        save_markdown(brief_md, brief_path)

        # 9. Mark seen in dedup
        if dedup:
            for article in cleaned:
                dedup.mark_seen(article.url, article.title, article.source_name)

        # 10. Record history
        brief_date = date.today().isoformat()
        if config.history.enabled:
            history = BriefHistory(config.history)
            history.cleanup_old()

        # 11. Push
        push_results = {}
        adapters = create_push_adapters(config)
        if adapters:
            logger.info("推送简报...")
            push_results = push_brief(
                adapters,
                brief_md,
                brief_date,
                {
                    "total_articles": len(summaries),
                    "executive_summary": exec_summary,
                },
            )
            stats.push_results = push_results

        # Record to history after push (so push status is included)
        if config.history.enabled:
            sources_used = list({a.source_name for a in cleaned})
            history.record_brief(
                brief_date=brief_date,
                file_path=str(brief_path),
                total_articles=len(summaries),
                executive_summary=exec_summary,
                sources_used=sources_used,
                push_status=push_results,
            )

        logger.info("=== 完成 ===")
        logger.info(f"  日报路径: {brief_path}")
        logger.info(f"  文章总数: {len(cleaned)}, 摘要总数: {len(summaries)}")

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        errors.append(str(e))

    stats.errors = errors
    stats.completed_at = datetime.now(timezone.utc)
    stats.duration_seconds = (
        stats.completed_at - stats.started_at
    ).total_seconds()

    # Record health
    health = HealthTracker()
    health.record_run(stats)

    return stats


def main():
    parser = argparse.ArgumentParser(description="AIWaveBrief — AI 资讯日报")
    parser.add_argument("--daemon", action="store_true", help="以定时任务模式运行")
    parser.add_argument("--history", action="store_true", help="查看历史简报")
    parser.add_argument("--date", type=str, help="查看指定日期的简报 (YYYY-MM-DD)")
    parser.add_argument("--search", type=str, help="搜索历史简报")
    parser.add_argument("--health", action="store_true", help="查看运行状态")
    args = parser.parse_args()

    load_env()
    config = load_config()
    setup_logging(config.logging)

    if args.health:
        health = HealthTracker()
        health.print_health()
        return

    if args.history or args.date or args.search:
        history = BriefHistory(config.history)
        if args.search:
            history.print_search(args.search)
        elif args.date:
            history.print_brief(args.date)
        else:
            history.print_list()
        return

    if args.daemon:
        from src.scheduler import BriefScheduler

        logger = logging.getLogger("AIWaveBrief")
        logger.info("启动定时调度模式...")
        scheduler = BriefScheduler(config, run_pipeline)
        scheduler.start()
        return

    run_pipeline(config)


if __name__ == "__main__":
    main()
