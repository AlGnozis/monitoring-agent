"""Notification adapter contract + mock implementation.

`NotifyAdapter.send_notification` is a locked public signature (CLAUDE.md § Rules #4).
The mock renders a real RFC-822 message to `outbox/{ref}.eml` (ref = entry id) so the
result is inspectable without any SMTP server. A real SMTP adapter would use `ref`
as the Message-ID / correlation id.
"""

from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from app.config import get_settings
from app.logger import log_info


class NotifyAdapter(Protocol):
    def send_notification(self, *, to: str, subject: str, body: str, ref: str) -> None:
        """Send a notification; `ref` correlates the message (entry id)."""
        ...


class MockNotifyAdapter:
    def __init__(self, outbox_dir: Path | None = None) -> None:
        self.outbox_dir = outbox_dir or get_settings().outbox_path

    def send_notification(self, *, to: str, subject: str, body: str, ref: str) -> None:
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        msg = EmailMessage()
        msg["From"] = "monitoring-agent@local"
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = f"<{ref}@monitoring-agent>"
        msg.set_content(body)

        path = self.outbox_dir / f"{ref}.eml"
        path.write_bytes(bytes(msg))
        log_info(f"wrote {path.name}", "MockNotifyAdapter", "notify.sent", {"to": to, "ref": ref})
