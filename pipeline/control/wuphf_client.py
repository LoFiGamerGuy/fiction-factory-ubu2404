"""WUPHFClient — workspace communication + wiki wrapper for the WUPHF API.

Reads WUPHF_API_URL and WUPHF_API_KEY from the environment (via python-dotenv).
All HTTP errors are caught and logged; methods are no-ops when env vars are absent
so the pipeline continues when WUPHF is unavailable.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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

    def __init__(self, wiki_root: str | Path | None = None) -> None:
        self._api_url: str = os.environ.get("WUPHF_API_URL", "").rstrip("/")
        self._api_key: str = os.environ.get("WUPHF_API_KEY", "")
        env_wiki_root = os.environ.get("WUPHF_WIKI_ROOT", "")
        self._wiki_root: Path | None = (
            Path(wiki_root or env_wiki_root) if wiki_root or env_wiki_root else None
        )
        self._auto_commit: bool = os.environ.get("WUPHF_WIKI_AUTO_COMMIT", "").lower() in {
            "1",
            "true",
            "yes",
        }
        self._configured: bool = bool(self._api_url and self._api_key)
        if not self._configured and self._wiki_root is None:
            logger.warning(
                "WUPHFClient: WUPHF_API_URL or WUPHF_API_KEY not set; "
                "operating in graceful-degradation mode (all calls are no-ops)."
            )

    # ── internal helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def _local_page_path(self, page: str) -> Path:
        if self._wiki_root is None:
            raise ValueError("WUPHF local wiki root is not configured")
        page_path = Path(page)
        if page_path.is_absolute() or ".." in page_path.parts:
            raise ValueError(f"WUPHF wiki page must be a relative slug: {page!r}")
        if not page_path.suffix:
            page_path = page_path.with_suffix(".md")
        return self._wiki_root / page_path

    def _write_local_wiki(self, page: str, content: str) -> None:
        path = self._local_page_path(page)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if self._auto_commit:
            self._commit_local_wiki(path)

    def _read_local_wiki(self, page: str) -> str | None:
        path = self._local_page_path(page)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def _commit_local_wiki(self, path: Path) -> None:
        if self._wiki_root is None:
            return
        git_check = subprocess.run(
            ["git", "-C", str(self._wiki_root), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if git_check.returncode != 0:
            return

        rel_path = path.relative_to(self._wiki_root).as_posix()
        add_result = subprocess.run(
            ["git", "-C", str(self._wiki_root), "add", "--", rel_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if add_result.returncode != 0:
            logger.warning("WUPHFClient: local wiki git add failed: %s", add_result.stderr.strip())
            return

        diff_result = subprocess.run(
            ["git", "-C", str(self._wiki_root), "diff", "--cached", "--quiet", "--", rel_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if diff_result.returncode == 0:
            return

        commit_result = subprocess.run(
            [
                "git",
                "-C",
                str(self._wiki_root),
                "commit",
                "-m",
                f"Update WUPHF wiki page {rel_path}",
                "--",
                rel_path,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if commit_result.returncode != 0:
            logger.warning(
                "WUPHFClient: local wiki git commit failed: %s",
                commit_result.stderr.strip(),
            )

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
        if self._wiki_root is not None:
            self._write_local_wiki(page, content)
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
        if self._wiki_root is not None:
            local_content = self._read_local_wiki(page)
            if local_content is not None:
                return local_content
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
