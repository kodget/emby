"""
Provider-agnostic LLM client for Emby.

Emby previously called Google Gemini directly from ai_service.py. This module replaces
that with any OpenAI-compatible chat-completions endpoint, so the platform can run on
free / open-weight models (Groq, Cerebras, OpenRouter, Together, a local vLLM, ...)
without touching a single call site.

Everything is driven from .env:

    LLM_BASE_URL        e.g. https://api.groq.com/openai/v1
    LLM_API_KEY         provider key
    LLM_MODEL           primary model            (default: openai/gpt-oss-120b)
    LLM_FALLBACK_MODEL  used when the primary model is rate-limited or unavailable

Free tiers are metered tightly (Groq allows 8k tokens/minute), so a single provider is a
single point of failure once real classes are online. Additional providers can therefore
be layered in without code changes — each is OpenAI-compatible and entirely optional:

    LLM_BACKUP_1_BASE_URL / LLM_BACKUP_1_API_KEY / LLM_BACKUP_1_MODEL
    LLM_BACKUP_2_BASE_URL / LLM_BACKUP_2_API_KEY / LLM_BACKUP_2_MODEL

Requests walk the provider chain in order and only fail once every provider has been
exhausted, so adding a Cerebras or OpenRouter key to .env immediately multiplies headroom.

Design notes
------------
* Uses `requests`, which is already a dependency — no new packages to install or deploy.
* Retries on 429 and 5xx with exponential backoff, honouring Retry-After when present,
  then drops to the fallback model, then to the next provider.
* `json_schema=` uses the provider's strict structured-output mode when available and
  degrades to json_object for providers that lack it.
* Vision is supported. The primary text model is text-only, so any request carrying an
  image is routed to LLM_VISION_MODEL (a multimodal sibling on the same provider) via
  `chat_with_image`. Callers that have no image keep using the faster text model.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Iterable, NamedTuple

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_FALLBACK_MODEL = "qwen/qwen3.8-27b"
# Multimodal sibling used only for requests that carry an image. gpt-oss-120b is
# text-only, so slide screenshots are routed here instead of being dropped.
DEFAULT_VISION_MODEL = "qwen/qwen3.8-27b"
DEFAULT_TIMEOUT = 90

_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4


class LLMNotConfigured(RuntimeError):
    """Raised when no LLM credentials are available."""


class LLMError(RuntimeError):
    """Raised when the provider could not produce a completion."""


class RequestTooLarge(LLMError):
    """Raised when the prompt exceeds the provider's token limits (HTTP 413)."""


def _setting(name: str, default: str = "") -> str:
    try:
        from django.conf import settings

        value = getattr(settings, name, None)
        if value:
            return str(value)
    except Exception:  # pragma: no cover - settings not ready
        pass
    import os

    return os.getenv(name, default)


def base_url() -> str:
    return (_setting("LLM_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")


def api_key() -> str:
    return _setting("LLM_API_KEY", "")


def primary_model() -> str:
    return _setting("LLM_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL


def fallback_model() -> str:
    return _setting("LLM_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL) or DEFAULT_FALLBACK_MODEL


class Provider(NamedTuple):
    name: str
    base_url: str
    api_key: str
    model: str
    fallback_model: str


def providers() -> list[Provider]:
    """Ordered provider chain: primary first, then any configured backups.

    Backups are optional. Configuring none leaves behaviour identical to a single
    provider; configuring one or more adds automatic failover when a free tier is
    exhausted, which is the expected steady state once whole classes are online.
    """
    chain: list[Provider] = []

    key = api_key()
    if key:
        chain.append(
            Provider(
                name=_provider_name(base_url()),
                base_url=base_url(),
                api_key=key,
                model=primary_model(),
                fallback_model=fallback_model(),
            )
        )

    for slot in (1, 2, 3):
        b_key = _setting(f"LLM_BACKUP_{slot}_API_KEY", "")
        b_url = _setting(f"LLM_BACKUP_{slot}_BASE_URL", "")
        if not (b_key and b_url):
            continue
        b_url = b_url.rstrip("/")
        b_model = _setting(f"LLM_BACKUP_{slot}_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
        chain.append(
            Provider(
                name=_provider_name(b_url),
                base_url=b_url,
                api_key=b_key,
                model=b_model,
                fallback_model=_setting(f"LLM_BACKUP_{slot}_FALLBACK_MODEL", "") or "",
            )
        )

    return chain


def _provider_name(url: str) -> str:
    host = url.split("//")[-1].split("/")[0]
    for known in ("groq", "cerebras", "openrouter", "together", "deepinfra", "nebius", "openai"):
        if known in host:
            return known
    return host


def vision_model() -> str:
    """Model to use when a request includes an image.

    The primary text model (gpt-oss-120b) is text-only, so image-bearing requests are
    routed to a multimodal sibling on the same provider. Set LLM_VISION_MODEL to empty
    to disable vision entirely; callers then fall back to text-only context.
    """
    return _setting("LLM_VISION_MODEL", DEFAULT_VISION_MODEL)


def supports_vision() -> bool:
    return bool(vision_model()) and bool(providers())


def is_configured() -> bool:
    """True when at least one LLM endpoint is usable."""
    return bool(providers())


def _timeout() -> int:
    try:
        return int(_setting("LLM_TIMEOUT", str(DEFAULT_TIMEOUT)) or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def _models_to_try(model: str | None) -> list[str]:
    chosen = model or primary_model()
    chain = [chosen]
    fb = fallback_model()
    if fb and fb != chosen:
        chain.append(fb)
    return chain


def _build_response_format(
    json_schema: dict[str, Any] | None,
    schema_name: str,
) -> dict[str, Any] | None:
    if not json_schema:
        return None
    return {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "strict": True, "schema": json_schema},
    }


def chat(
    messages: Iterable[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    json_schema: dict[str, Any] | None = None,
    schema_name: str = "response",
    json_object: bool = False,
    return_usage: bool = False,
) -> Any:
    """Run a chat completion and return the assistant's text.

    Args:
        messages: OpenAI-style [{"role": ..., "content": ...}].
        model: override the configured primary model.
        json_schema: strict structured-output schema; the reply is guaranteed JSON.
        json_object: ask for valid JSON without a fixed schema.

    Raises:
        LLMNotConfigured: no API key configured.
        LLMError: every model and retry failed.
    """
    chain = providers()
    if not chain:
        raise LLMNotConfigured(
            "No LLM provider is configured. Add LLM_BASE_URL / LLM_API_KEY / LLM_MODEL "
            "to backend/.env to enable AI features."
        )

    payload_base: dict[str, Any] = {
        "messages": list(messages),
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }
    response_format = _build_response_format(json_schema, schema_name)
    if response_format:
        payload_base["response_format"] = response_format
    elif json_object:
        payload_base["response_format"] = {"type": "json_object"}

    last_error = "unknown error"

    for provider in chain:
        url = f"{provider.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        for candidate in _provider_models(provider, model):
            payload = dict(payload_base, model=candidate)
            content, last_error, fatal, total_tokens = _try_model(url, headers, payload, last_error)
            if content is not None:
                if return_usage:
                    return content, total_tokens
                return content
            logger.warning(
                "LLM %s/%s failed: %s", provider.name, candidate, last_error
            )
            if fatal:
                break  # provider-level problem (bad key, dead host) — move on

    raise LLMError(f"LLM request failed across all providers: {last_error}")


def _provider_models(provider: Provider, override: str | None) -> list[str]:
    if override:
        return [override]
    chain = [provider.model]
    if provider.fallback_model and provider.fallback_model != provider.model:
        chain.append(provider.fallback_model)
    return chain


def _try_model(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    last_error: str,
) -> tuple[str | None, str, bool, int]:
    """Attempt one model with retries. Returns (content, error, provider_is_dead, total_tokens)."""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=_timeout())
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            _sleep_backoff(attempt, None)
            continue

        if resp.status_code == 200:
            try:
                resp_json = resp.json()
                content = resp_json["choices"][0]["message"]["content"] or ""
                total_tokens = resp_json.get("usage", {}).get("total_tokens", 0)
            except (ValueError, KeyError, IndexError) as exc:
                return None, f"malformed response: {exc}", False, 0
            if content.strip():
                return content, last_error, False, total_tokens
            last_error = "empty completion"
            _sleep_backoff(attempt, None)
            continue

        # Some providers reject strict schemas for some models; degrade and retry once.
        if resp.status_code == 400 and payload.get("response_format", {}).get(
            "type"
        ) == "json_schema":
            logger.warning("Structured output rejected, degrading to json_object")
            payload["response_format"] = {"type": "json_object"}
            continue

        last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
        if resp.status_code == 413:
            raise RequestTooLarge(last_error)  # prompt too large, skip retries and bubble up
        if resp.status_code in (401, 402, 403, 404):
            return None, last_error, True, 0  # credentials/host/quota problem: skip provider
        if resp.status_code in _RETRY_STATUS:
            _sleep_backoff(attempt, resp.headers.get("Retry-After"))
            continue
        return None, last_error, False, 0

    return None, last_error, False, 0


def chat_json(
    messages: Iterable[dict[str, str]],
    *,
    json_schema: dict[str, Any] | None = None,
    schema_name: str = "response",
    default: Any = None,
    **kwargs: Any,
) -> Any:
    """chat() that parses the reply as JSON, tolerating markdown fences.

    Returns `default` instead of raising when the reply cannot be parsed.
    """
    try:
        raw = chat(
            messages,
            json_schema=json_schema,
            schema_name=schema_name,
            json_object=json_schema is None,
            **kwargs,
        )
    except (LLMNotConfigured, LLMError):
        raise

    return parse_json(raw, default=default)


def parse_json(raw: str, default: Any = None) -> Any:
    """Best-effort JSON parse of a model reply."""
    text = strip_fences(raw)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass

    # Salvage the outermost JSON object or array if the model added prose around it.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (ValueError, TypeError):
                continue

    logger.warning("Could not parse LLM JSON reply: %s", text[:200])
    return default


def strip_fences(text: str) -> str:
    """Remove ```json fences some models wrap structured replies in."""
    text = (text or "").strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _sleep_backoff(attempt: int, retry_after: str | None) -> None:
    if retry_after:
        try:
            time.sleep(min(float(retry_after), 20.0))
            return
        except (TypeError, ValueError):
            pass
    time.sleep(min(2**attempt + random.random(), 12.0))


def describe() -> dict[str, Any]:
    """Small diagnostic payload for health checks and the admin UI."""
    chain = providers()
    return {
        "configured": bool(chain),
        "supports_vision": supports_vision(),
        "vision_model": vision_model() or None,
        "providers": [
            {
                "name": p.name,
                "base_url": p.base_url,
                "model": p.model,
                "fallback_model": p.fallback_model or None,
            }
            for p in chain
        ],
    }


def chat_with_image(
    prompt: str,
    image_b64: str,
    *,
    mime_type: str = "image/jpeg",
    system: str | None = None,
    max_tokens: int = 1200,
    temperature: float = 0.4,
    return_usage: bool = False,
) -> Any:
    """Run a completion that includes an image.

    Routed to the multimodal model rather than the primary text one. Raises
    LLMNotConfigured when vision is unavailable so callers can fall back to text.
    """
    if not supports_vision():
        raise LLMNotConfigured("No vision-capable model is configured.")

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                },
            ],
        }
    )

    return chat(
        messages,
        model=vision_model(),
        temperature=temperature,
        max_tokens=max_tokens,
        return_usage=return_usage,
    )
