from __future__ import annotations

import json
from urllib import error, request


class DiscordWebhookSender:
    """Send plain text messages to a Discord webhook."""

    def __init__(self, webhook_url: str, timeout_seconds: float = 10.0) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def send(self, content: str) -> None:
        if not self.webhook_url:
            raise ValueError("Webhook URL is required")
        if not content.strip():
            raise ValueError("Message content cannot be empty")
        if len(content) > 2000:
            raise ValueError("Discord message content cannot exceed 2000 characters")

        payload = json.dumps({"content": content}).encode("utf-8")
        req = request.Request(
            self.webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "DiscordAutoMessage/1.0",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status >= 300:
                    raise RuntimeError(
                        f"Discord webhook returned unexpected status code: {response.status}"
                    )
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Discord webhook request failed with HTTP {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Discord webhook request failed: {exc.reason}") from exc
