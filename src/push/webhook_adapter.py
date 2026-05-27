import json
import logging
import urllib.request
import urllib.error

from ..models import PushChannelConfig
from .base import PushAdapter

logger = logging.getLogger(__name__)


class WebhookPushAdapter(PushAdapter):
    def __init__(self, config: PushChannelConfig):
        self.url = config.url
        self.headers = config.headers

    @property
    def name(self) -> str:
        return "webhook"

    def validate_config(self) -> bool:
        return bool(self.url)

    def send(self, brief_markdown: str, brief_date: str, metadata: dict) -> bool:
        if not self.validate_config():
            logger.warning("Webhook push adapter not configured, skipping")
            return False

        try:
            payload = json.dumps(
                {
                    "date": brief_date,
                    "content": brief_markdown,
                    "total_articles": metadata.get("total_articles", 0),
                    "executive_summary": metadata.get("executive_summary", ""),
                },
                ensure_ascii=False,
            ).encode("utf-8")

            headers = {"Content-Type": "application/json", **self.headers}
            req = urllib.request.Request(
                self.url, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status < 300:
                    logger.info(f"Webhook push succeeded: {resp.status}")
                    return True
                else:
                    logger.warning(f"Webhook returned status {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Webhook push failed: {e}")
            return False
