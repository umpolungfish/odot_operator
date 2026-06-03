"""
odot — The ⊙perator.

A self-verifying agentic loop where every action is paired with a verification step
that enforces the Frobenius condition: mu(delta(query)) == query.

DeepSeek integration (updated 2026-07-01):
  - Direct DeepSeek API (current): OdotAgent(model="deepseek:deepseek-v4-flash")
  - Direct DeepSeek API (premium): OdotAgent(model="deepseek:deepseek-v4-pro")
  - OpenRouter (DeepSeek R1):      OdotAgent(model="openrouter:deepseek/deepseek-r1")
  - Local (Ollama):               OdotAgent(model="ollama:llama3.2")
  - ⚠ deepseek-chat / deepseek-reasoner deprecated (sunset 2026/07/24)

Quick start:
    from odot import OdotAgent
    agent = OdotAgent(model="deepseek:deepseek-v4-flash")
    result = agent.run_sync("Your task here")
"""

from .agent import OdotAgent, LoopCycle, DualToolResult, LoopPhase
from .tools import DEFAULT_TOOL_SCHEMAS, DEFAULT_EMIT_FNS, DEFAULT_VERIFY_FNS
from .provider import (
    resolve_provider,
    DeepSeekProvider,
    OpenRouterProvider,
    LocalProvider,
    HttpProvider,
    LLMProvider,
    strip_think_blocks,
    query_model,
)

__all__ = [
    "OdotAgent",
    "LoopCycle",
    "DualToolResult",
    "LoopPhase",
    "DEFAULT_TOOL_SCHEMAS",
    "DEFAULT_EMIT_FNS",
    "DEFAULT_VERIFY_FNS",
    "resolve_provider",
    "DeepSeekProvider",
    "OpenRouterProvider",
    "LocalProvider",
    "HttpProvider",
    "LLMProvider",
    "strip_think_blocks",
    "query_model",
]
__version__ = "0.2.1"
