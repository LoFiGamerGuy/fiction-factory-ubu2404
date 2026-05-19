"""WUPHFClient — workspace communication + wiki wrapper for the WUPHF API.

Reads WUPHF_API_URL and WUPHF_API_KEY from the environment (via python-dotenv).
All HTTP errors are caught and logged; methods are no-ops when env vars are absent
so the pipeline continues when WUPHF is unavailable.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10.0


@dataclass
class ActivityEvent:
    """A single event from the WUPHF activity stream."""

    event_id: str
    timestamp: str
    actor: str
    action: str
    resource: str
    metadata: dict[str, Any] = field(default_factory=dict)


class WUPHFClient:
    """Thin wrapper around the WUPHF channel-messaging and wiki REST API."""

    def __init__(self) -> None:
        self._api_url: str = os.environ.get("WUPHF_API_URL", "").rstrip("/")
        self._api_key: str = os.environ.get("WUPHF_API_KEY", "")
        self._configured: bool = bool(self._api_url and self._api_key)
        if not self._configured:
            logger.warning(
                "WUPHFClient: WUPHF_API_URL or WUPHF_API_KEY not set; "
                "operating in graceful-degradation mode (all calls are no-ops)."
            )

    # ── internal helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    # ── public API ──────────────────────────────────────────────────────────────

    def post_to_channel(
        self,
        channel: str,
        message: str,
        room: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """POST /channels/{channel}/messages."""
        if not self._configured:
            return
        payload: dict[str, Any] = {"message": message}
        if room is not None:
            payload["room"] = room
        if metadata is not None:
            payload["metadata"] = metadata
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(
                    f"{self._api_url}/channels/{channel}/messages",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "WUPHFClient.post_to_channel(%s) HTTP error: %s — ignoring", channel, exc
            )

    def update_wiki(
        self,
        page: str,
        content: str,
        author: str = "pipeline",
    ) -> None:
        """PUT /wiki/{page} to create or update a wiki page."""
        if not self._configured:
            return
        payload: dict[str, Any] = {"content": content, "author": author}
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.put(
                    f"{self._api_url}/wiki/{page}",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("WUPHFClient.update_wiki(%s) HTTP error: %s — ignoring", page, exc)

    def read_wiki(self, page: str) -> str:
        """GET /wiki/{page}; returns empty string if the page is not found or on error."""
        if not self._configured:
            return ""
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.get(
                    f"{self._api_url}/wiki/{page}",
                    headers=self._headers(),
                )
                if resp.status_code == 404:
                    return ""
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return str(data.get("content", ""))
        except httpx.HTTPError as exc:
            logger.warning("WUPHFClient.read_wiki(%s) HTTP error: %s — returning ''", page, exc)
            return ""

    def get_activity_stream(self, since: datetime) -> list[ActivityEvent]:
        """GET /activity?since=ISO; returns empty list on error or when unconfigured."""
        if not self._configured:
            return []
        since_str = since.isoformat()
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.get(
                    f"{self._api_url}/activity",
                    params={"since": since_str},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                events_raw: list[dict[str, Any]] = resp.json()
                return [
                    ActivityEvent(
                        event_id=str(ev.get("event_id", "")),
                        timestamp=str(ev.get("timestamp", "")),
                        actor=str(ev.get("actor", "")),
                        action=str(ev.get("action", "")),
                        resource=str(ev.get("resource", "")),
                        metadata=dict(ev.get("metadata", {})),
                    )
                    for ev in events_raw
                ]
        except httpx.HTTPError as exc:
            logger.warning(
                "WUPHFClient.get_activity_stream(since=%s) HTTP error: %s — returning []",
                since_str,
                exc,
            )
            return []
