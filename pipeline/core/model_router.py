"""ModelRouter — multi-provider LLM routing with Instructor structured output.

Every LLM call goes through this module. Raw text responses are never returned;
every call returns a validated pydantic model (via Instructor).

Routing: tier_defaults in model_router.json maps (provider, tier) → model name.
Cost logging: every call is appended to cost_log.jsonl.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

ResponseT = TypeVar("ResponseT", bound=BaseModel)

# Approximate cost per 1K tokens (USD). Updated in Phase 14 for exact pricing.
_COST_PER_1K: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-opus-4-7": {"input": 0.015, "output": 0.075},
    "gpt-4.1-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "phi3.5": {"input": 0.0, "output": 0.0},
}


class ModelRouter:
    """Routes LLM calls to the correct provider/model, wrapping every call with Instructor.

    Config is loaded from ``model_router.json`` at ``config_path``.
    Cost log is written to ``cost_log_path`` if provided.
    """

    def __init__(
        self,
        config_path: Path,
        cost_log_path: Path | None = None,
    ) -> None:
        self._config: dict[str, Any] = json.loads(config_path.read_text())
        self._cost_log_path = cost_log_path

    # ── Routing ───────────────────────────────────────────────────────────────

    def route(self, provider: str, tier: str) -> str:
        """Return the model name for the given provider and tier.

        Looks up ``tier_defaults[tier][provider]`` in model_router.json.
        """
        tier_defaults: dict[str, dict[str, str]] = self._config.get("tier_defaults", {})
        tier_map = tier_defaults.get(tier, {})
        if provider not in tier_map:
            raise ValueError(
                f"No model configured for provider={provider!r}, tier={tier!r}. "
                f"Check tier_defaults in model_router.json."
            )
        return tier_map[provider]

    def active_tier(self) -> str:
        """Return the active model tier from config (default: 'test')."""
        return str(self._config.get("model_tier", "test"))

    # ── Structured call (Instructor-wrapped) ──────────────────────────────────

    def call(
        self,
        messages: list[dict[str, str]],
        response_model: type[ResponseT],
        provider: str,
        seed: int = 0,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        job_id: str = "",
        agent_id: str = "",
    ) -> ResponseT:
        """Call the LLM and return a validated pydantic model.

        Never returns raw text. Raises if provider is unknown.
        Logs cost to cost_log.jsonl if cost_log_path was provided.
        """
        tier = self.active_tier()
        model = self.route(provider, tier)
        start = time.monotonic()

        if provider == "anthropic":
            result = self._call_anthropic(messages, response_model, model, max_tokens, temperature)
        elif provider == "openai":
            result = self._call_openai(
                messages, response_model, model, max_tokens, temperature, seed
            )
        elif provider == "ollama":
            result = self._call_ollama(messages, response_model, model, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider!r}")

        duration_ms = (time.monotonic() - start) * 1000
        self._append_cost_log(
            job_id=job_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
        )
        return result

    # ── Provider dispatch ─────────────────────────────────────────────────────

    def _call_anthropic(
        self,
        messages: list[dict[str, str]],
        response_model: type[ResponseT],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> ResponseT:
        try:
            import anthropic as _anthropic  # noqa: PLC0415
            import instructor  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(f"Missing dependency: {exc}") from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise OSError("ANTHROPIC_API_KEY not set")

        client = instructor.from_anthropic(_anthropic.Anthropic(api_key=api_key))

        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        chat_messages = [m for m in messages if m.get("role") != "system"]
        system_text = "\n".join(system_parts)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
            "response_model": response_model,
        }
        if system_text:
            kwargs["system"] = system_text

        return client.messages.create(**kwargs)  # type: ignore[no-any-return]

    def _call_openai(
        self,
        messages: list[dict[str, str]],
        response_model: type[ResponseT],
        model: str,
        max_tokens: int,
        temperature: float,
        seed: int,
    ) -> ResponseT:
        try:
            import instructor  # noqa: PLC0415
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(f"Missing dependency: {exc}") from exc

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise OSError("OPENAI_API_KEY not set")

        client = instructor.from_openai(OpenAI(api_key=api_key))

        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            seed=seed,
            messages=messages,  # type: ignore[arg-type]
            response_model=response_model,
        )

    def _call_ollama(
        self,
        messages: list[dict[str, str]],
        response_model: type[ResponseT],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> ResponseT:
        try:
            import instructor  # noqa: PLC0415
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(f"Missing dependency: {exc}") from exc

        cfg = self._config.get("providers", {}).get("ollama", {})
        base_url_env = cfg.get("base_url_env", "OLLAMA_HOST")
        base_url = os.environ.get(
            base_url_env, cfg.get("base_url_default", "http://localhost:11434")
        )
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        client = instructor.from_openai(
            OpenAI(base_url=base_url, api_key="ollama"),
            mode=instructor.Mode.JSON,
        )

        return client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,  # type: ignore[arg-type]
            response_model=response_model,
        )

    # ── Cost logging ──────────────────────────────────────────────────────────

    def _append_cost_log(
        self,
        job_id: str,
        agent_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float,
    ) -> None:
        if self._cost_log_path is None:
            return
        pricing = _COST_PER_1K.get(model, {"input": 0.0, "output": 0.0})
        cost_usd = (
            input_tokens / 1000.0 * pricing["input"] + output_tokens / 1000.0 * pricing["output"]
        )
        import datetime  # noqa: PLC0415

        entry = {
            "job_id": job_id,
            "agent_id": agent_id,
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 8),
            "duration_ms": round(duration_ms, 1),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        try:
            self._cost_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._cost_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.warning("Cost log write failed (non-fatal): %s", exc)
