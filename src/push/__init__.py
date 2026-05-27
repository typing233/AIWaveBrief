import logging

from ..models import AppConfig, PushChannelConfig
from .base import PushAdapter
from .email_adapter import EmailPushAdapter
from .webhook_adapter import WebhookPushAdapter

logger = logging.getLogger(__name__)

ADAPTER_REGISTRY: dict[str, type[PushAdapter]] = {
    "email": EmailPushAdapter,
    "webhook": WebhookPushAdapter,
}


def create_push_adapters(config: AppConfig) -> list[PushAdapter]:
    if not config.push.enabled:
        return []

    adapters = []
    for channel in config.push.channels:
        adapter_cls = ADAPTER_REGISTRY.get(channel.type)
        if not adapter_cls:
            logger.warning(f"Unknown push channel type: {channel.type}")
            continue
        adapter = adapter_cls(channel)
        if adapter.validate_config():
            adapters.append(adapter)
        else:
            logger.warning(f"Push adapter '{channel.type}' not properly configured")
    return adapters


def push_brief(
    adapters: list[PushAdapter],
    brief_markdown: str,
    brief_date: str,
    metadata: dict,
) -> dict[str, bool]:
    results = {}
    for adapter in adapters:
        try:
            results[adapter.name] = adapter.send(brief_markdown, brief_date, metadata)
        except Exception as e:
            logger.error(f"Push adapter '{adapter.name}' raised: {e}")
            results[adapter.name] = False
    return results
