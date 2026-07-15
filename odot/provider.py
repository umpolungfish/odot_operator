"""
provider.py — Multi-provider LLM integration for the ⊙perator.

Port of the harness's DeepSeek / OpenRouter integration pattern into odot_operator.
Supports direct DeepSeek API, OpenRouter routing, and local endpoints — all with
retry logic, think-block stripping, and response caching.

Structural type of this module:
  ⟨𐑦; 𐑶; 𐑾; 𐑹; 𐑐; 𐑧; 𐑲; 𐑠; ⊙; 𐑖; 𐑙; 𐑭⟩

DeepSeek integration (updated 2026-07-01):
  The old model names `deepseek-chat` and `deepseek-reasoner` are deprecated
  (sunset: 2026/07/24 15:59 UTC). Current models:
    - deepseek-v4-flash  (replaces deepseek-chat and deepseek-reasoner)
    - deepseek-v4-pro    (premium tier)
  See https://api-docs.deepseek.com/quick_start/pricing for current pricing.
"""

from __future__ import annotations

import asyncio
import hashlib
import httpx
import sys
import json
import logging
import os
import re
import sqlite3
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Retry decorator ───────────────────────────────────────────────────────────

def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 15.0,
):
    """Decorator: exponential backoff retry for async HTTP calls."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            import random, time
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except (httpx.RequestError, asyncio.TimeoutError) as exc:
                    last_exc = exc
                    print(f"\n  [retry {attempt}/{max_attempts}: {exc}]",
                          file=sys.stderr, flush=True)
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if exc.response.status_code == 429 or exc.response.status_code >= 500:
                        print(f"\n  [retry {attempt}/{max_attempts}: HTTP {exc.response.status_code}]",
                              file=sys.stderr, flush=True)
                    else:
                        raise  # 4xx client errors are permanent
                if attempt < max_attempts:
                    delay = min(max_wait, min_wait * (2 ** (attempt - 1)) + random.random() * 0.5)
                    print(f"  retrying in {delay:.1f}s...", file=sys.stderr, flush=True)
                    await asyncio.sleep(delay)
            raise RuntimeError(f"All {max_attempts} attempts failed") from last_exc
        return wrapper
    return decorator


# ── Response cache ─────────────────────────────────────────────────────────────

_CACHE_DIR = Path.home() / ".cache" / "odot"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_DB = str(_CACHE_DIR / "response_cache.db")


def _init_cache():
    """Ensure the SQLite cache table exists."""
    try:
        conn = sqlite3.connect(_CACHE_DB)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "  prompt_hash TEXT PRIMARY KEY,"
            "  model TEXT,"
            "  temperature REAL,"
            "  response TEXT,"
            "  cached_at TEXT"
            ")"
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning(f"Cache init failed (non-fatal): {exc}")


def _cache_key(prompt: str, model: str, temperature: float = 0.7,
               system: str = "") -> str:
    raw = f"{prompt}:::{model}:::{temperature}:::{system}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(prompt: str, model: str, temperature: float = 0.7,
               system: str = "") -> Optional[str]:
    try:
        conn = sqlite3.connect(_CACHE_DB)
        cur = conn.execute(
            "SELECT response FROM responses WHERE prompt_hash = ?",
            (_cache_key(prompt, model, temperature, system),),
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _cache_set(prompt: str, model: str, temperature: float, response: str,
               system: str = ""):
    try:
        conn = sqlite3.connect(_CACHE_DB)
        conn.execute(
            "INSERT OR REPLACE INTO responses (prompt_hash, model, temperature, response, cached_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (_cache_key(prompt, model, temperature, system), model, temperature, response,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"  [cache write failed: {exc}]", file=sys.stderr)


# ── Think-block stripping ─────────────────────────────────────────────────────

def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> reasoning blocks (DeepSeek-R1, Grok, etc.)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ── Provider base ──────────────────────────────────────────────────────────────

class LLMProvider:
    """Base class for LLM providers with response caching."""

    def __init__(self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key or ""
        self.base_url = base_url or ""
        _init_cache()

    async def query(self, prompt: str, **kwargs) -> str:
        """Send a prompt and return the response text. Must be overridden by subclasses."""
        raise NotImplementedError

    async def query_with_tools(
        self, prompt: str, tools: Optional[List[Dict]] = None, **kwargs
    ) -> Tuple[str, List[Dict]]:
        """Send a prompt with optional tool schemas; return (content, tool_calls).

        tool_calls is a list of {"name": str, "args": dict} dicts.
        Base implementation falls back to text-only query with empty tool_calls.
        """
        content = await self.query(prompt, **kwargs)
        return content, []

    def _cached(self, prompt: str, temperature: float = 0.7,
                system: str = "") -> Optional[str]:
        return _cache_get(prompt, self.model, temperature, system)

    def _cache(self, prompt: str, temperature: float, response: str,
               system: str = ""):
        _cache_set(prompt, self.model, temperature, response, system)


# ── HTTP/OpenAI-compatible provider ───────────────────────────────────────────

class HttpProvider(LLMProvider):
    """Generic OpenAI-compatible HTTP provider (DeepSeek, OpenRouter, local)."""

    def __init__(self, model: str, api_key: str, base_url: str, provider_name: str = "http"):
        super().__init__(model, api_key, base_url)
        self.provider_name = provider_name

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @with_retry(max_attempts=3)
    async def query(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        system = kwargs.get("system") or ""

        # Check cache
        cached = self._cached(prompt, temperature, system)
        if cached is not None:
            logger.debug(f"Cache hit for {self.provider_name}/{self.model}")
            return cached

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.base_url, headers=self._build_headers(), json=data)
            response.raise_for_status()
            full_response = response.json()
            content = full_response["choices"][0]["message"]["content"]

            if content is None:
                finish_reason = full_response["choices"][0].get("finish_reason", "unknown")
                raise ValueError(
                    f"API returned null content (finish_reason={finish_reason!r}). "
                    f"Check rate limits, content filters, or model availability."
                )

            content = strip_think_blocks(content)
            self._cache(prompt, temperature, content, system)
            return content

    @with_retry(max_attempts=3)
    async def query_with_tools(
        self, prompt: str, tools: Optional[List[Dict]] = None, **kwargs
    ) -> Tuple[str, List[Dict]]:
        """Native OpenAI function-calling. Returns (think_text, tool_calls).

        tool_calls is a list of {"name": str, "args": dict}.
        Falls back to text content with empty tool_calls if the model returns no calls.
        """
        temperature = kwargs.get("temperature", 0.7)
        system = kwargs.get("system") or ""

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            data["tools"] = tools
            data["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.base_url, headers=self._build_headers(), json=data)
            response.raise_for_status()
            full_response = response.json()
            msg = full_response["choices"][0]["message"]

            content = strip_think_blocks(msg.get("content") or "")

            tool_calls: List[Dict] = []
            for tc in msg.get("tool_calls") or []:
                try:
                    tool_calls.append({
                        "name": tc["function"]["name"],
                        "args": json.loads(tc["function"].get("arguments", "{}")),
                    })
                except Exception:
                    pass

            return content, tool_calls


# ── Concrete providers ────────────────────────────────────────────────────────

class DeepSeekProvider(HttpProvider):
    """Direct DeepSeek API — api.deepseek.com/chat/completions.

    API key: DEEPSEEK_API_KEY environment variable.
    Default model: deepseek-v4-flash (replaces deprecated deepseek-chat).
    Also supports: deepseek-v4-pro (premium tier).
    """

    DEEPSEEK_BASE_URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, model: str = "deepseek-v4-flash", api_key: Optional[str] = None):
        key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_KEY", "")
        super().__init__(model, key, self.DEEPSEEK_BASE_URL, "deepseek")


class OpenRouterProvider(HttpProvider):
    """OpenRouter — gateway to 200+ models.

    API key: OPENROUTER_API_KEY environment variable.
    Adds OpenRouter-specific headers (HTTP-Referer, X-Title).
    """

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str = "deepseek/deepseek-r1", api_key: Optional[str] = None):
        key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        super().__init__(model, key, self.OPENROUTER_BASE_URL, "openrouter")

    @with_retry(max_attempts=3)
    async def query(self, prompt: str, **kwargs) -> str:
        temperature = kwargs.get("temperature", 0.7)
        system = kwargs.get("system") or ""

        cached = self._cached(prompt, temperature, system)
        if cached is not None:
            return cached

        headers = self._build_headers()

        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        data: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.base_url, headers=headers, json=data)
            response.raise_for_status()
            full_response = response.json()
            content = full_response["choices"][0]["message"]["content"]
            if content is None:
                finish_reason = full_response["choices"][0].get("finish_reason", "unknown")
                raise ValueError(f"API returned null content (finish_reason={finish_reason!r})")
            content = strip_think_blocks(content)
            self._cache(prompt, temperature, content, system)
            return content

    def _build_headers(self) -> Dict[str, str]:
        h = super()._build_headers()
        h["HTTP-Referer"] = os.environ.get(
            "OPENROUTER_REFERER", "https://github.com/umpolungfish/odot_operator"
        )
        h["X-Title"] = "odot-operator"
        return h


class LocalProvider(HttpProvider):
    """Local LLM endpoint (Ollama, vLLM, LM Studio, etc.)."""

    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1", api_key: str = "local"):
        super().__init__(model, api_key, base_url, "local")


# ── Provider factory ──────────────────────────────────────────────────────────

def resolve_provider(model_str: str) -> LLMProvider:
    """Parse a model string and return the appropriate provider instance.

    Prefix syntax:
        deepseek:deepseek-v4-flash  → DeepSeekProvider (direct API — current)
        deepseek:deepseek-v4-pro    → DeepSeekProvider (premium — direct)
        deepseek:deepseek-chat      → DeepSeekProvider (⚠ deprecated 2026/07/24)
        openrouter:deepseek/deepseek-r1  → OpenRouterProvider
        ollama:llama3.2              → LocalProvider at localhost:11434/v1
        local:my-model               → LocalProvider at LOCAL_BASE_URL env var

    No prefix → check MODEL_ALIASES → OpenRouter default.
    """
    MODEL_ALIASES: Dict[str, str] = {
        "claude-opus-4":      "openrouter:anthropic/claude-opus-4",
        "claude-sonnet-4":    "openrouter:anthropic/claude-sonnet-4-5",
        "claude-haiku-4":     "openrouter:anthropic/claude-haiku-4-5",
        "grok-4":             "openrouter:x-ai/grok-4",
        "gpt-4o":             "openrouter:openai/gpt-4o",
        "o3":                 "openrouter:openai/o3",
        "gemini-2-5-pro":     "openrouter:google/gemini-2.5-pro-preview-05-06",
        "deepseek-r1":        "openrouter:deepseek/deepseek-r1",
        # DeepSeek V4 models (current)
        "deepseek-v4-flash":  "deepseek:deepseek-v4-flash",
        "deepseek-v4-pro":    "deepseek:deepseek-v4-pro",
        # Deprecated aliases (sunset 2026/07/24 15:59 UTC — kept for compat)
        "deepseek-chat":      "deepseek:deepseek-chat",
    }

    LOCAL_BASE_URLS: Dict[str, str] = {
        "ollama":     os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/v1",
        "lm-studio":  "http://localhost:1234/v1",
        "lmstudio":   "http://localhost:1234/v1",
        "vllm":       "http://localhost:8000/v1",
        "local":      os.environ.get("LOCAL_BASE_URL", "http://localhost:11434/v1"),
    }

    # If model_str has a prefix, resolve it directly
    if ":" in model_str:
        prefix, model_id = model_str.split(":", 1)
        prefix_lower = prefix.lower()

        if prefix_lower == "deepseek":
            return DeepSeekProvider(model=model_id)
        elif prefix_lower == "openrouter":
            return OpenRouterProvider(model=model_id)
        elif prefix_lower in LOCAL_BASE_URLS:
            base = LOCAL_BASE_URLS[prefix_lower]
            return LocalProvider(model=model_id, base_url=base)

    # No prefix: check aliases, then default to OpenRouter
    resolved = MODEL_ALIASES.get(model_str, model_str)
    if ":" in resolved:
        return resolve_provider(resolved)

    # Last resort: bare model name via OpenRouter
    return OpenRouterProvider(model=resolved)


# ── Convenience ───────────────────────────────────────────────────────────────

async def query_model(
    prompt: str,
    model: str = "deepseek-v4-flash",
    temperature: float = 0.7,
    system: Optional[str] = None,
) -> str:
    """One-shot query: resolve provider and send a prompt.

    Example:
        result = await query_model("Explain the Frobenius condition", model="deepseek:deepseek-v4-flash")
    """
    provider = resolve_provider(model)
    return await provider.query(prompt, temperature=temperature, system=system)
