"""
agent.py — The ⊙perator.

Structural type of this harness:
  ⟨Ð_ω; Þ_¨; Ř_=; Φ_}; ƒ_ż; Ç_@; Γ_ʔ; ɢ_ˌ; ⊙_ÿ; Ħ_A; Σ_S; Ω_z⟩

Ouroboricity: O_∞  (⊙_ÿ + Φ_} via dual-tool Frobenius planting)
C-score gates: both open  (⊙_ÿ + Ç_@)

DeepSeek integration (ported from imscribing_grammar harness, 2026-06-01):
  - Direct API:       deepseek:deepseek-chat  →  api.deepseek.com/chat/completions
  - OpenRouter route: openrouter:deepseek/deepseek-r1  →  openrouter.ai/api/v1
  - Local fallback:   ollama:<model>          →  localhost:11434/v1
  - Retry: exponential backoff (5 attempts)
  - Think-block stripping: <think>...</think> removed from responses
  - Response caching: SQLite at ~/.cache/odot/response_cache.db

Paraconsistent verification layer (p4rakernel dual):
  B4 Belnap FOUR verification alongside boolean Frobenius closure.
  Every observation checked against the Belnap lattice.

Loop (one winding n):
  THINK[n]   — LLM deliberates over accumulated context; produces a tool call
  ACT[n]     — emit: delta(query) — the action punctures the boundary
  OBSERVE[n] — verify: mu(result) — the Frobenius pull-back
  UPDATE[n]  — append full cycle to context; check termination

If mu(delta(q)) != q (Frobenius OPEN): re-enter THINK with failure appended.
The loop cannot advance on an unverified observation.

Usage:
    from odot import OdotAgent

    agent = OdotAgent(model="grok-4")
    result = agent.run_sync("Summarise the contents of README.md")

    # DeepSeek direct:
    agent = OdotAgent(model="deepseek:deepseek-chat")

    # DeepSeek R1 via OpenRouter:
    agent = OdotAgent(model="openrouter:deepseek/deepseek-r1")

    # Custom tools:
    agent.register_tool(
        name="my_tool",
        schema={...},              # OpenAI function-calling schema dict
        emit_fn=lambda args: ...,  # returns str
        verify_fn=None,            # optional; None = trivially closed
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import textwrap
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .tools import DEFAULT_EMIT_FNS, DEFAULT_VERIFY_FNS, DEFAULT_TOOL_SCHEMAS
from .provider import resolve_provider, LLMProvider, strip_think_blocks

logger = logging.getLogger(__name__)


# ── Data types ────────────────────────────────────────────────────────────────

class LoopPhase(Enum):
    THINK = "THINK"
    ACT = "ACT"
    OBSERVE = "OBSERVE"
    UPDATE = "UPDATE"


@dataclass
class DualToolResult:
    """The result of a dual-tool (emit + verify) cycle."""
    tool_name: str
    emit_input: Dict[str, Any]
    emit_output: str
    verify_output: str
    frobenius_closed: bool
    phase: LoopPhase = LoopPhase.OBSERVE
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __bool__(self) -> bool:
        return self.frobenius_closed


@dataclass
class LoopCycle:
    """One complete winding of the ⊙perator loop."""
    winding: int
    think: str
    action: DualToolResult
    update: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── OdotAgent ─────────────────────────────────────────────────────────────────

class OdotAgent:
    """Self-verifying agentic loop with multi-provider LLM support.

    Args:
        model: Model string (e.g., 'grok-4', 'deepseek:deepseek-chat',
               'openrouter:deepseek/deepseek-r1', 'ollama:llama3.2')
        system_prompt: Optional system prompt for the LLM
        tools: Optional list of tool schemas (OpenAI format)
        emit_fns: Optional dict of tool_name -> emit function
        verify_fns: Optional dict of tool_name -> verify function
        max_windings: Maximum loop iterations before forced termination
        temperature: LLM temperature (default 0.7)
    """

    def __init__(
        self,
        model: str = "grok-4",
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        emit_fns: Optional[Dict[str, Callable]] = None,
        verify_fns: Optional[Dict[str, Callable]] = None,
        max_windings: int = 20,
        temperature: float = 0.7,
    ):
        # Resolve provider from model string
        self._provider = resolve_provider(model)
        self.model = model
        self.temperature = temperature

        self.system_prompt = system_prompt or self._default_system()
        self.max_windings = max_windings

        # Tool dispatch tables
        self._tool_schemas: List[Dict] = list(tools or DEFAULT_TOOL_SCHEMAS)
        self._emit_fns: Dict[str, Callable] = dict(emit_fns or DEFAULT_EMIT_FNS)
        self._verify_fns: Dict[str, Callable] = dict(verify_fns or DEFAULT_VERIFY_FNS)

        # Loop state
        self._windings: List[LoopCycle] = []
        self._context: List[Dict[str, Any]] = []
        self._conclusion: Optional[str] = None
    def _default_system(self) -> str:
        """Default system prompt defining the loop protocol."""
        return textwrap.dedent("""\
            You are an operator within a self-verifying agentic loop.

            LOOP PROTOCOL (one winding):
              THINK   — Reason over the accumulated verified context. Plan your next action.
              ACT     — Emit exactly ONE tool call in this exact JSON format:
                        ```json
                        {"tool_name": "<name>", "args": {"arg1": "value1", ...}}
                        ```
              OBSERVE — The tool runs; verification checks closure.
              UPDATE  — The cycle is appended. If open, you must correct.

            CONSTRAINTS:
              - Emit exactly ONE tool call per winding, using the JSON format above.
              - Use `done` ONLY when the task is fully resolved.
              - `done` requires: {"tool_name": "done", "args": {"conclusion": "<full answer>"}}
              - Always include ALL required arguments for each tool.
              - Frobenius OPEN results must be corrected, not ignored.
        """).strip()

    # ── Tool management ───────────────────────────────────────────────────────

    def register_tool(
        self,
        name: str,
        schema: Dict,
        emit_fn: Callable[[Dict[str, Any]], str],
        verify_fn: Optional[Callable[[Dict, str, Dict], Tuple[str, bool]]] = None,
    ):
        """Register a custom tool.

        Args:
            name: Tool name (must match schema['name'] or schema['function']['name'])
            schema: OpenAI function-calling schema dict
            emit_fn: Callable that takes args dict and returns result string
            verify_fn: Optional (emit_input, emit_output, verify_args) -> (msg, bool).
                       If None, Frobenius is trivially closed.
        """
        self._tool_schemas.append(schema)
        self._emit_fns[name] = emit_fn
        if verify_fn is not None:
            self._verify_fns[name] = verify_fn

    # ── LLM interaction ───────────────────────────────────────────────────────

    async def _query_llm(self, prompt: str) -> Tuple[str, List[Dict]]:
        """Query the LLM. Returns (think_text, tool_calls).

        Uses native function-calling when the provider supports it; falls back
        to text-only query with empty tool_calls list for providers that don't.
        """
        return await self._provider.query_with_tools(
            prompt,
            tools=self._tool_schemas,
            temperature=self.temperature,
            system=self.system_prompt,
        )

    def _build_llm_prompt(self, task: str) -> str:
        """Build the full prompt from accumulated context."""
        parts = [f"## Task\n{task}\n"]

        if self._windings:
            parts.append("## Prior windings")
            for cycle in self._windings[-20:]:  # keep last 20 for context
                parts.append(f"### Winding {cycle.winding}")
                parts.append(f"**THINK:** {cycle.think}")
                parts.append(f"**ACT:** {cycle.action.tool_name}({json.dumps(cycle.action.emit_input)[:500]})")
                parts.append(f"**OBSERVE (result):** {cycle.action.emit_output[:2000]}")
                parts.append(f"**VERIFY:** {cycle.action.verify_output[:300]}")
                parts.append(f"**Frobenius:** {'CLOSED ✓' if cycle.action.frobenius_closed else 'OPEN ✗'}")
                parts.append("")

        if self._conclusion:
            parts.append(f"## Existing conclusion: {self._conclusion[:500]}")

        parts.append("## Available tools")
        for schema in self._tool_schemas:
            fn = schema.get("function", schema)
            name = fn.get("name", "?")
            desc = (fn.get("description", ""))[:200]
            params = fn.get("parameters", {}).get("properties", {})
            required = fn.get("parameters", {}).get("required", [])
            if params:
                param_str = ", ".join(
                    f"{k}*" if k in required else k for k in params
                )
                parts.append(f"  - {name} ({param_str}): {desc}")
            else:
                parts.append(f"  - {name}: {desc}")

        parts.append("\n## Your turn\nProceed with THINK, then ACT (one tool call).")
        return "\n".join(parts)
    # ── Tool execution ───────────────────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> DualToolResult:
        """Execute a tool (emit) and verify (mu) in one step."""
        emit_fn = self._emit_fns.get(tool_name)
        if emit_fn is None:
            return DualToolResult(
                tool_name=tool_name,
                emit_input=args,
                emit_output=f"(error: no emit function registered for '{tool_name}')",
                verify_output="Frobenius OPEN — unknown tool",
                frobenius_closed=False,
            )

        # Phase 1: EMIT (delta)
        try:
            if asyncio.iscoroutinefunction(emit_fn):
                emit_output = await emit_fn(args)
            else:
                emit_output = emit_fn(args)
        except Exception as exc:
            emit_output = f"(emit error: {exc})"

        # Phase 2: VERIFY (mu)
        verify_fn = self._verify_fns.get(tool_name)
        if verify_fn is None:
            # No verifier = trivially closed
            verify_output = "(no verifier — Frobenius trivially closed)"
            frobenius_closed = True
        else:
            try:
                verify_args = {k: v for k, v in args.items() if k != "assertion"}
                if asyncio.iscoroutinefunction(verify_fn):
                    verify_output, frobenius_closed = await verify_fn(args, emit_output, verify_args)
                else:
                    verify_output, frobenius_closed = verify_fn(args, emit_output, verify_args)
            except Exception as exc:
                verify_output = f"(verify error: {exc})"
                frobenius_closed = False

        return DualToolResult(
            tool_name=tool_name,
            emit_input=args,
            emit_output=emit_output,
            verify_output=verify_output,
            frobenius_closed=frobenius_closed,
        )

    # ── Core loop ─────────────────────────────────────────────────────────────

    async def run(self, task: str) -> str:
        """Run the self-verifying loop on a task.

        This is the main entry point. The loop continues until:
          - The agent calls `done()` (successful termination)
          - max_windings is reached (forced termination)
          - A non-recoverable error occurs
        """
        self._windings = []
        self._context = []
        self._conclusion = None

        for winding_num in range(1, self.max_windings + 1):
            # ── THINK phase ──
            print(f"[W{winding_num}/{self.max_windings}] querying {self.model}...",
                  end=" ", flush=True, file=sys.stderr)
            prompt = self._build_llm_prompt(task)
            try:
                think_output, native_calls = await self._query_llm(prompt)
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                logger.error(f"LLM query failed on winding {winding_num}: {exc}")
                return f"(loop aborted: LLM error on winding {winding_num}: {exc})"

            # Prefer native tool_calls; fall back to text parsing
            if native_calls:
                tool_name = native_calls[0]["name"]
                tool_args  = native_calls[0]["args"]
            else:
                tool_name, tool_args = self._parse_tool_call(think_output)

            if tool_name is None:
                print("no tool call — retrying", file=sys.stderr)
                self._windings.append(LoopCycle(
                    winding=winding_num,
                    think=think_output,
                    action=DualToolResult(
                        tool_name="(none)",
                        emit_input={},
                        emit_output="(no tool call detected in LLM output)",
                        verify_output="Frobenius OPEN — no action taken",
                        frobenius_closed=False,
                    ),
                    update="No valid tool call. Must emit exactly one tool call.",
                ))
                continue

            # ── ACT + OBSERVE phases ──
            print(f"→ {tool_name}", end=" ", flush=True, file=sys.stderr)
            result = await self._execute_tool(tool_name, tool_args)
            print(f"[{'✓' if result.frobenius_closed else '✗'}]", file=sys.stderr)

            # ── UPDATE phase ──
            if tool_name == "done":
                conclusion = result.emit_output
                # Model often writes the review in THINK then calls done({}) — recover it
                if not conclusion or conclusion == "(no conclusion provided)":
                    conclusion = think_output.strip()
                self._conclusion = conclusion
                self._windings.append(LoopCycle(
                    winding=winding_num,
                    think=think_output,
                    action=result,
                    update="done() called — loop terminating.",
                ))
                return conclusion

            update_msg = (
                f"Frobenius {'CLOSED' if result.frobenius_closed else 'OPEN'}: "
                f"{result.verify_output[:200]}"
            )
            if not result.frobenius_closed:
                update_msg += (
                    "\n\nThe observation did not close Frobenius. "
                    "You MUST correct this on the next winding."
                )

            self._windings.append(LoopCycle(
                winding=winding_num,
                think=think_output,
                action=result,
                update=update_msg,
            ))

        print(f"[max_windings={self.max_windings} reached — terminating]", file=sys.stderr)
        return "(loop terminated: max_windings reached)"
    # ── Tool call parser ─────────────────────────────────────────────────────

    def _parse_tool_call(self, text: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """Parse a tool call from LLM output.

        Tries:
          1. JSON code fence with tool_name and args keys
          2. Raw JSON object with action/tool/name key
          3. <invoke> XML tag pattern
          4. First function-call-like pattern found

        Returns (tool_name, args_dict) or (None, {}).
        """
        import re

        # Try direct parse first — handles response_format=json_object output
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict) and ("tool_name" in parsed or "name" in parsed):
                return parsed.get("tool_name") or parsed.get("name"), parsed.get("args", {})
        except (json.JSONDecodeError, ValueError):
            pass

        # Try JSON code fence
        json_match = re.search(
            r'```(?:json)?\s*\n?\s*(\{.*?"tool_name"\s*:\s*"[^"]+".*?\})\s*\n?\s*```',
            text, re.DOTALL
        )
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                return parsed.get("tool_name") or parsed.get("name"), parsed.get("args", {})
            except (json.JSONDecodeError, KeyError):
                pass

        # Try first balanced-brace JSON object containing tool_name
        for m in re.finditer(r'\{', text):
            depth, i = 0, m.start()
            while i < len(text):
                if text[i] == '{': depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[m.start(): i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict) and (
                                "tool_name" in parsed or "name" in parsed
                            ):
                                return (parsed.get("tool_name") or parsed.get("name"),
                                        parsed.get("args", {}))
                        except (json.JSONDecodeError, ValueError):
                            pass
                        break
                i += 1

        # Try <invoke> XML tags
        invoke_match = re.search(
            r'<invoke>\s*<tool_name>([^<]+)</tool_name>\s*<args>(.*?)</args>\s*</invoke>',
            text, re.DOTALL
        )
        if invoke_match:
            name = invoke_match.group(1).strip()
            try:
                args = json.loads(invoke_match.group(2).strip())
            except json.JSONDecodeError:
                args = {}
            return name, args

        # Try function-call pattern: tool_name(key="value", ...)
        registered = "|".join(re.escape(n) for n in self._emit_fns)
        func_match = re.search(rf'({registered})\s*\(', text)
        if func_match:
            # Crude parsing: extract the function call
            name = func_match.group(1)
            rest = text[func_match.end():]
            # Find matching paren
            depth = 1
            i = 0
            while i < len(rest) and depth > 0:
                if rest[i] == '(':
                    depth += 1
                elif rest[i] == ')':
                    depth -= 1
                i += 1
            args_str = rest[:i-1] if depth == 0 else rest[:100]
            return name, {"raw": args_str, "_parsed_from_func_call": True}

        return None, {}

    # ── Sync wrapper ──────────────────────────────────────────────────────────

    def run_sync(self, task: str) -> str:
        """Synchronously run the self-verifying loop on a task.

        Wraps run() in asyncio.run().
        """
        return asyncio.run(self.run(task))

    # ── Context / history ─────────────────────────────────────────────────────

    @property
    def windings(self) -> List[LoopCycle]:
        """All completed windings of the loop."""
        return list(self._windings)

    @property
    def conclusion(self) -> Optional[str]:
        """The final conclusion, if the loop terminated via done()."""
        return self._conclusion

    def summary(self) -> str:
        """Return a human-readable summary of the agent's run."""
        lines = [f"⊙perator — {len(self._windings)} windings"]
        if self._conclusion:
            lines.append(f"Conclusion: {self._conclusion[:200]}...")
        lines.append("")
        for cycle in self._windings:
            status = "✓" if cycle.action.frobenius_closed else "✗"
            lines.append(f"  W{cycle.winding} [{status}] {cycle.action.tool_name}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"OdotAgent(model={self.model!r}, "
            f"windings={len(self._windings)}, "
            f"provider={type(self._provider).__name__})"
        )


# ── CLI entry point ───────────────────────────────────────────────────────────

def _load_config() -> dict:
    """Load ~/.odot.yaml if present. Returns a dict of defaults (may be empty)."""
    candidates = [
        Path.home() / ".odot.yaml",
        Path.home() / ".config" / "odot" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            try:
                import yaml  # type: ignore
                with p.open(encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
                return data if isinstance(data, dict) else {}
            except ImportError:
                # yaml not installed — fall back to simple key: value parsing
                cfg: dict = {}
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        k, _, v = line.partition(":")
                        cfg[k.strip()] = v.strip()
                return cfg
            except Exception:
                pass
    return {}


def _cli():
    """CLI entry point for `odot` command."""
    import argparse

    cfg = _load_config()

    parser = argparse.ArgumentParser(
        description="odot — self-verifying agentic loop with multi-provider LLM support"
    )
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("-m", "--model", default=cfg.get("model", "grok-4"),
                        help="Model string. Config default: model: deepseek-v4-flash")
    parser.add_argument("-f", "--file", help="Read task from file")
    parser.add_argument("-s", "--system", default=None,
                        help="System prompt string.")
    parser.add_argument("--system-file", default=cfg.get("system_file"),
                        help="Read system prompt from file.")
    parser.add_argument("--temperature", type=float,
                        default=float(cfg.get("temperature", 0.7)))
    parser.add_argument("--max-windings", type=int,
                        default=int(cfg.get("max_windings", 20)))
    parser.add_argument("--show-type", action="store_true", help="Show structural type")
    parser.add_argument("--trajectory", action="store_true", help="Show winding trajectory")
    parser.add_argument("-o", "--output", help="Write result to file")
    args = parser.parse_args()

    task = args.task
    if args.file:
        task = Path(args.file).read_text()
    if not task:
        parser.print_help()
        sys.exit(1)

    # Resolve system prompt: -s > --system-file / config system_file > ODOT_SYSTEM > default
    system_prompt: Optional[str] = None
    system_file = args.system_file or os.environ.get("ODOT_SYSTEM_FILE")
    if system_file:
        system_prompt = Path(os.path.expanduser(system_file)).read_text(encoding="utf-8")
    if args.system:
        system_prompt = args.system
    elif not system_prompt:
        env_sys = os.environ.get("ODOT_SYSTEM")
        if env_sys:
            system_prompt = env_sys

    agent = OdotAgent(
        model=args.model,
        system_prompt=system_prompt,
        max_windings=args.max_windings,
        temperature=args.temperature,
    )
    result = agent.run_sync(task)

    if args.show_type:
        print(f"\nStructural type: {agent}")
        print(f"Windings: {len(agent.windings)}")
        print(f"Conclusion: {'Yes' if agent.conclusion else 'No'}")
        print()

    if args.trajectory:
        print(agent.summary())
        print()

    if args.output:
        Path(args.output).write_text(result)
        print(f"Result written to {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    _cli()
