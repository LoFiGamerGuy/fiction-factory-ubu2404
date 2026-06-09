"""PaperclipClient — budget-tracking and approval-gate wrapper for the Paperclip REST API.

Reads PAPERCLIP_API_URL and PAPERCLIP_API_KEY from the environment (via python-dotenv).
All HTTP errors are caught; safe defaults are returned so the pipeline continues when
Paperclip is unavailable.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TIMEOUT_S = 10.0
_POLL_INTERVAL_S = 5.0


class PaperclipClient:
    """Thin wrapper around the Paperclip budget / approval REST API."""

    def __init__(self) -> None:
        self._api_url: str = os.environ.get("PAPERCLIP_API_URL", "").rstrip("/")
        self._api_key: str = os.environ.get("PAPERCLIP_API_KEY", "")
        self._configured: bool = bool(self._api_url and self._api_key)
        if not self._configured:
            logger.warning(
                "PaperclipClient: PAPERCLIP_API_URL or PAPERCLIP_API_KEY not set; "
                "operating in graceful-degradation mode (all budget/approval checks pass)."
            )

    # ── internal helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    # ── public API ──────────────────────────────────────────────────────────────

    def check_budget(self, agent_role: str) -> bool:
        """Return True if the agent_role has remaining budget.

        Returns True (pass-through) when Paperclip is not configured or unreachable.
        """
        if not self._configured:
            return True
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.get(
                    f"{self._api_url}/budgets/{agent_role}/check",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                remaining: float = float(data.get("remaining", 1.0))
                return remaining > 0
        except httpx.HTTPError as exc:
            logger.warning(
                "PaperclipClient.check_budget(%s) HTTP error: %s — returning True (pass-through)",
                agent_role,
                exc,
            )
            return True

    def record_cost(self, agent_role: str, cost_usd: float, tokens_used: int = 0) -> None:
        """POST /costs to record a cost event for agent_role."""
        if not self._configured:
            return
        payload: dict[str, Any] = {
            "agent_role": agent_role,
            "cost_usd": cost_usd,
            "tokens_used": tokens_used,
        }
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(
                    f"{self._api_url}/costs",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "PaperclipClient.record_cost(%s, %.4f) HTTP error: %s — ignoring",
                agent_role,
                cost_usd,
                exc,
            )

    def request_approval(
        self,
        gate_name: str,
        context: dict[str, Any],
        timeout_s: int = 3600,
    ) -> bool:
        """Submit an approval request and poll until approved/rejected/timeout.

        Returns True when approved or Paperclip is not configured.
        Returns False when rejected or timed out. Returns True on HTTP errors
        (graceful degradation).
        """
        if not self._configured:
            return True
        payload: dict[str, Any] = {"gate_name": gate_name, "context": context}
        approval_id: str | None = None
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(
                    f"{self._api_url}/approvals",
                    json=payload,
                    headers=self._headers(),
                )
                resp.raise_for_status()
                approval_id = str(resp.json().get("approval_id", ""))
        except httpx.HTTPError as exc:
            logger.warning(
                "PaperclipClient.request_approval(%s) POST error: %s — returning True",
                gate_name,
                exc,
            )
            return True

        if not approval_id:
            logger.warning(
                "PaperclipClient.request_approval(%s): no approval_id in response — returning True",
                gate_name,
            )
            return True

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with httpx.Client(timeout=_TIMEOUT_S) as client:
                    poll = client.get(
                        f"{self._api_url}/approvals/{approval_id}",
                        headers=self._headers(),
                    )
                    poll.raise_for_status()
                    status: str = str(poll.json().get("status", "pending"))
            except httpx.HTTPError as exc:
                logger.warning(
                    "PaperclipClient.request_approval(%s) poll error: %s — returning True",
                    gate_name,
                    exc,
                )
                return True

            if status == "approved":
                return True
            if status == "rejected":
                logger.info(
                    "PaperclipClient.request_approval(%s): rejected by Paperclip", gate_name
                )
                return False
            time.sleep(_POLL_INTERVAL_S)

        logger.warning(
            "PaperclipClient.request_approval(%s): timed out after %ds — returning False",
            gate_name,
            timeout_s,
        )
        return False

    def heartbeat(self) -> bool:
        """GET /health; returns True if healthy, True on error (graceful degradation)."""
        if not self._configured:
            return True
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.get(
                    f"{self._api_url}/health",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return True
        except httpx.HTTPError as exc:
            logger.warning(
                "PaperclipClient.heartbeat() HTTP error: %s — returning True (pass-through)", exc
            )
            return True
