import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from ..models import PushChannelConfig
from .base import PushAdapter

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE_PATH = Path("templates/email_template.html")


class EmailPushAdapter(PushAdapter):
    def __init__(self, config: PushChannelConfig):
        self.smtp_host = config.smtp_host
        self.smtp_port = config.smtp_port
        self.smtp_ssl = config.smtp_ssl
        self.smtp_user = config.smtp_user
        self.smtp_password = config.smtp_password
        self.from_addr = config.from_addr
        self.to_addrs = config.to_addrs

    @property
    def name(self) -> str:
        return "email"

    def validate_config(self) -> bool:
        return bool(
            self.smtp_host and self.from_addr and self.to_addrs and self.smtp_user
        )

    def send(self, brief_markdown: str, brief_date: str, metadata: dict) -> bool:
        if not self.validate_config():
            logger.warning("Email push adapter not configured, skipping")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"AI Wave Brief — {brief_date}"
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            msg.attach(MIMEText(brief_markdown, "plain", "utf-8"))

            html_body = self._render_html(brief_markdown, brief_date, metadata)
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            if self.smtp_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                server.starttls()

            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            server.quit()

            logger.info(f"Email sent to {', '.join(self.to_addrs)}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def _render_html(self, markdown: str, brief_date: str, metadata: dict) -> str:
        if EMAIL_TEMPLATE_PATH.exists():
            template = EMAIL_TEMPLATE_PATH.read_text(encoding="utf-8")
            return (
                template.replace("{{date}}", brief_date)
                .replace("{{content}}", self._md_to_html(markdown))
                .replace(
                    "{{total_articles}}", str(metadata.get("total_articles", ""))
                )
            )
        return f"<html><body><pre>{markdown}</pre></body></html>"

    def _md_to_html(self, markdown: str) -> str:
        import re

        html = markdown
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"((?:<li>.*</li>\n?)+)", r"<ul>\1</ul>", html)
        html = re.sub(r"\n{2,}", "<br><br>", html)
        html = re.sub(r"^---$", "<hr>", html, flags=re.MULTILINE)
        return html
