from abc import ABC, abstractmethod


class PushAdapter(ABC):
    @abstractmethod
    def send(self, brief_markdown: str, brief_date: str, metadata: dict) -> bool:
        """Send the brief. Returns True on success."""
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """Check if adapter is properly configured."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter display name for logging."""
        ...
