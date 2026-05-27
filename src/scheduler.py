import logging
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .models import AppConfig

logger = logging.getLogger(__name__)


class BriefScheduler:
    def __init__(self, config: AppConfig, run_pipeline_fn):
        self.config = config
        self.run_pipeline_fn = run_pipeline_fn
        self._stop_event = threading.Event()

        hour, minute = config.schedule.time.split(":")
        self.trigger = CronTrigger(
            hour=int(hour),
            minute=int(minute),
            timezone=config.schedule.timezone,
        )
        self.scheduler = BackgroundScheduler(timezone=config.schedule.timezone)

    def start(self):
        self.scheduler.add_job(
            self._execute,
            trigger=self.trigger,
            id="daily_brief",
            name="每日简报生成",
            misfire_grace_time=3600,
            coalesce=True,
        )
        self.scheduler.start()

        next_run = self.scheduler.get_job("daily_brief").next_run_time
        logger.info(
            f"调度器已启动 — 每日 {self.config.schedule.time} "
            f"({self.config.schedule.timezone}) 执行"
        )
        logger.info(f"下次执行时间: {next_run}")

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._stop_event.wait()

    def get_next_run_time(self) -> str | None:
        job = self.scheduler.get_job("daily_brief")
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None

    def _execute(self):
        logger.info("=== 定时任务触发: 开始生成简报 ===")
        try:
            self.run_pipeline_fn(self.config)
        except Exception as e:
            logger.error(f"定时任务执行失败: {e}")

    def _signal_handler(self, signum, frame):
        logger.info("收到停止信号，正在关闭调度器...")
        self.shutdown()

    def shutdown(self):
        self.scheduler.shutdown(wait=False)
        self._stop_event.set()
        logger.info("调度器已关闭")
