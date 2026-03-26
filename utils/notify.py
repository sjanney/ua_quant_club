"""Optional Discord notifications."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def send(message: str) -> None:
    """POST ``message`` to ``DISCORD_WEBHOOK_URL`` if set; otherwise no-op.

    Args:
        message: Plain-text body.
    """
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return
    data = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except (urllib.error.URLError, TimeoutError, OSError):
        return
