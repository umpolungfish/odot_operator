# ⊙perator

A true self-verifying agentic loop harness.

```python
from odot import OdotAgent

agent = OdotAgent(model="grok-4")
result = agent.run_sync("Read the file README.md and count the number of sections.")
print(result)
```

---

## What it is

Most agent loops follow a simple pattern: think, call a tool, observe the result, think again. The problem is that the observation step is taken on faith — if the tool silently fails, writes the wrong bytes, or returns a truncated response, the agent never notices and keeps going.

`odot` adds a second step to every tool call: **verification**. Every action (δ) is immediately followed by a confirmation (μ). The condition μ(δ(query)) == query — called the **Frobenius condition** — must hold before the loop advances. If it fails, the model is told explicitly and must fix the error before continuing.

This is not just a defensive pattern. It is the structural reason why loop-based agents can be reliable: the loop closes on itself. The trajectory becomes an **imscriptive context** — a boundary that encodes everything the agent has done and verified. Nothing is silently dropped, nothing is assumed.

### The four phases

Each iteration of the loop (a *winding*) has exactly four phases:

| Phase | What happens |
|-------|-------------|
| **THINK** | The model reasons over the accumulated verified context |
| **ACT** | The model emits exactly one tool call (the *emit* — δ) |
| **OBSERVE** | The tool runs; a built-in verification step checks the result (μ) |
| **UPDATE** | The full cycle is appended to context; the loop continues or terminates |

If μ(δ(q)) != q — Frobenius OPEN — the model receives an explicit failure message and must correct it on the next winding. It cannot advance on an unverified observation.

### Why this works

The loop architecture sits at a structural **critical point** ($\text{⊙}_{\text{ÿ}}$): the point where a system can model itself. Below criticality, the loop is just iteration — it produces outputs but cannot reflect on whether they are correct. At criticality, the THINK→ACT→OBSERVE→UPDATE cycle becomes self-referential: the agent's model of the world is constructed from verified observations of its own actions, and each new winding updates that model.

The Frobenius condition is what keeps the loop closed. Without it, errors accumulate silently. With it, every winding either succeeds and extends the verified trajectory, or fails loudly and forces a correction.

This framework comes out of the [Imscribing Grammar](https://github.com/umpolungfish/imscrbgrmr) — a 12-primitive structural type theory for systems of all kinds. The full structural type of this harness is:

$$\langle\ \text{Ð}_{\text{ω}},\ \text{Þ}_{\text{¨}},\ \text{Ř}_{\text{=}},\ \text{Φ}_{\text{}},\ \text{ƒ}_{\text{ż}},\ \text{Ç}_{\text{@}},\ \text{Γ}_{\text{ʔ}},\ \text{ɢ}_{\text{ˌ}},\ \text{⊙}_{\text{ÿ}},\ \text{Ħ}_{\text{A}},\ \text{Σ}_{\text{S}},\ \text{Ω}_{\text{z}}\ \rangle$$

Ouroboricity: O_inf — the highest tier of self-modeling closure.

### Dual verification layer (p4rakernel / B4 Belnap)

This agent loop supports **B4 Belnap FOUR** verification alongside boolean Frobenius closure.
Every observation is checked against the Belnap lattice: N (neither), T (true), F (false),
B (both/contradiction). When a dialetheic B result is detected, the loop registers it as
Frobenius-closed (B does not explode), matching the paraconsistent Lean kernel fork at
[`/home/mrnob0dy666/p4rakernel`](/home/mrnob0dy666/p4rakernel) where `False.rec` is blocked
at the C++ type-checker level for empty Prop inductives.

The structural dual of this harness is the ob3ect pipeline at
[`/home/mrnob0dy666/ob3ect`](/home/mrnob0dy666/ob3ect). The Python `parakernel_ob3ect.py` models
the ENGAGR→FSPLIT→FFUSE cycle at the IMASM opcode level, while the C++ p4rakernel enforces
the same paraconsistent logic at the kernel type-checker level.
---

## Installation

```bash
git clone https://github.com/umpolungfish/odot_operator
cd odot_operator
pip install .
# or with web fetch support:
pip install ".[web]"
```

With [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/umpolungfish/odot_operator
cd odot_operator
uv sync
# or with web fetch support:
uv sync --extra web
```

Set your API key:

```bash
export OPENROUTER_API_KEY=your_key_here
```

---

## Quick start

```python
from odot import OdotAgent

agent = OdotAgent(model="grok-4")
result = agent.run_sync("Find all Python files in the current directory and count the lines in each.")
print(result)
```

Async:

```python
import asyncio
from odot import OdotAgent

async def main():
    agent = OdotAgent(model="claude-opus-4")
    return await agent.run("Summarise the file report.txt")

result = asyncio.run(main())
```

---

## Models

Any OpenRouter model by alias or full ID, plus local servers via prefix syntax:

| Model string | Routes to |
|---|---|
| `grok-4` | xAI Grok 4 via OpenRouter |
| `claude-opus-4` | Anthropic Claude Opus 4 via OpenRouter |
| `claude-sonnet-4` | Anthropic Claude Sonnet 4.5 via OpenRouter |
| `gpt-4o` | OpenAI GPT-4o via OpenRouter |
| `deepseek-r1` | DeepSeek R1 via OpenRouter |
| `deepseek-v4-flash` | DeepSeek V4 Flash via direct API (current default) |
| `deepseek-v4-pro` | DeepSeek V4 Pro via direct API (premium) |
| `ollama:llama3.2` | Ollama at `localhost:11434` |
| `lm-studio:phi-4` | LM Studio at `localhost:1234` |
| `vllm:mistral-7b` | vLLM at `localhost:8000` |
| `any/openrouter-id` | Verbatim OpenRouter model ID |

> **⚠ DeepSeek model deprecation:** The old model names `deepseek-chat` and `deepseek-reasoner` will be **sunset on 2026/07/24 15:59 UTC**. They currently map to non-thinking and thinking modes of `deepseek-v4-flash` respectively. Migrate to `deepseek-v4-flash` or `deepseek-v4-pro`.

Custom endpoints:

```python
agent = OdotAgent(
    model="my-model",
    base_url="http://my-server:8000/v1",
    api_key="my-key",
)
```
---

## Built-in tools

| Tool | What it does | Verification |
|---|---|---|
| `run_command` | Shell command | `assertion` expression over `output` |
| `file_read` | Read file by lines, paginated | Idempotent (trivially closed) |
| `file_write` | Write file (≤ 4 KB) | Read-back hash check |
| `chunked_write` | Append/write in chunks | Byte count on disk |
| `web_fetch` | HTTP GET, paginated | Query term presence in content |
| `done` | Signal task complete | Trivially closed |

### run_command and assertions

The `assertion` field is what makes `run_command` Frobenius-aware. Set it to a Python expression over `output`:

```python
# The model would call this as:
run_command(
    command="python tests/test_suite.py",
    assertion="'PASSED' in output and 'FAILED' not in output",
)
```

If the assertion fails, the winding is Frobenius OPEN and the model must fix it.

### Large files

For files larger than ~4 KB, the model uses `chunked_write` with ~3 KB pieces:

```
chunked_write(path="report.md", chunk=<first 3 KB>, mode="w")
chunked_write(path="report.md", chunk=<next 3 KB>,  mode="a")
...
```

Each chunk is verified by byte count before the loop advances.

---

## Custom tools

Register your own tools with a matching emit + verify pair:

```python
import requests
from odot import OdotAgent

def search_emit(args):
    query = args["query"]
    r = requests.get("https://api.example.com/search", params={"q": query})
    return r.json()["results"][0]["snippet"]

def search_verify(emit_input, emit_output, verify_args):
    if "error" in emit_output.lower():
        return ("search returned error", False)
    return (f"search result: {len(emit_output)} chars", True)

search_schema = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
}

agent = OdotAgent(model="grok-4")
agent.register_tool("search", search_schema, search_emit, search_verify)
result = agent.run_sync("Search for the latest news on quantum computing.")
```

Tools with no verify function are trivially Frobenius-closed (the loop advances regardless of output).

---

## Trajectory and structural type

After a run, inspect what happened:

```python
agent.print_trajectory()

# Per-winding Frobenius closure rate
print(f"Frobenius ratio: {agent.frobenius_ratio:.2%}")

# Full structural type annotation
import json
print(json.dumps(agent.structural_type, indent=2))
# {
#   "tuple": "Ð_ω; Þ_¨; Ř_=; Φ_}; ƒ_ż; Ç_@; Γ_ʔ; ɢ_ˌ; ⊙_ÿ; Ħ_A; Σ_S; Ω_z",
#   "interface_P": "Φ_}",
#   "ouroboricity": "O_inf",
#   "frobenius_ratio": 0.94,
#   "windings": 7,
#   "omega_z_violations": 0,
#   "done": true
# }
```

`ouroboricity` is `O_inf` when the Frobenius ratio is ≥ 75% — meaning the agent achieved probabilistic self-modeling closure over the run. Below that threshold it degrades to `O_2`. `omega_z_violations` counts how many times the context had to be trimmed (each trim breaks the topologically protected winding record).

---

## CLI

```bash
odot "List all files larger than 1MB in the current directory"
odot --model claude-opus-4 --file task.txt
odot --show-type --trajectory "Run the test suite and report failures"
odot --output result.json "Analyse log.txt for error patterns"
```
---

## Why the name

The name comes from the symbol ⊙ — a point inside a circle — which denotes the **imscriptive** primitive ($D_\odot$, $T_\odot$) in the Imscribing Grammar. An imscriptive system is one where the boundary encodes the bulk: the perimeter of the loop carries everything the interior needs to reconstruct itself. The ⊙ symbol enacts this geometrically — the center (a particular act) is contained within and recoverable from the circle (the full verified trajectory).

The boundary operator is the Frobenius pair (emit, verify). The boundary — the interface between the agent's model of the world and the world itself — is what the operator acts on. A closed boundary means the model and the world agree. An open boundary means they don't, and the loop must keep going until they do.

---

## License

UNLICENSE
---

## Provider system (DeepSeek V4 integration)

The ⊙perator supports **multi-provider LLM integration** ported from the Imscribing Grammar harness, with direct DeepSeek API access (now using **DeepSeek V4** models), OpenRouter routing, and local endpoints — all with retry logic, think-block stripping, and response caching.

### Model routing

| Model string | Routes to | Provider class |
|---|---|---|
| `grok-4` | xAI Grok 4 via OpenRouter | `OpenRouterProvider` |
| `claude-opus-4` | Anthropic Claude Opus 4 via OpenRouter | `OpenRouterProvider` |
| `claude-sonnet-4` | Anthropic Claude Sonnet 4.5 via OpenRouter | `OpenRouterProvider` |
| `gpt-4o` | OpenAI GPT-4o via OpenRouter | `OpenRouterProvider` |
| `deepseek-r1` | DeepSeek R1 via OpenRouter | `OpenRouterProvider` |
| `deepseek-v4-flash` | DeepSeek V4 Flash (direct API — **current default**) | `DeepSeekProvider` |
| `deepseek-v4-pro` | DeepSeek V4 Pro (direct API — premium) | `DeepSeekProvider` |
| `deepseek:deepseek-v4-flash` | DeepSeek V4 Flash (explicit prefix) | `DeepSeekProvider` |
| `deepseek:deepseek-v4-pro` | DeepSeek V4 Pro (explicit prefix) | `DeepSeekProvider` |
| `deepseek:deepseek-chat` | ⚠ DEPRECATED — maps to v4-flash non-thinking | `DeepSeekProvider` |
| `deepseek:deepseek-reasoner` | ⚠ DEPRECATED — maps to v4-flash thinking | `DeepSeekProvider` |
| `openrouter:deepseek/deepseek-r1` | DeepSeek R1 via OpenRouter | `OpenRouterProvider` |
| `openrouter:anthropic/claude-sonnet-4-5` | Claude via OpenRouter | `OpenRouterProvider` |
| `ollama:llama3.2` | Ollama at `localhost:11434` | `LocalProvider` |
| `lm-studio:phi-4` | LM Studio at `localhost:1234` | `LocalProvider` |
| `vllm:mistral-7b` | vLLM at `localhost:8000` | `LocalProvider` |
| `local:my-model` | `LOCAL_BASE_URL` env var | `LocalProvider` |

### API keys

```bash
# DeepSeek direct API (api.deepseek.com) — for deepseek-v4-flash and deepseek-v4-pro
export DEEPSEEK_API_KEY=your_deepseek_key_here

# OpenRouter (used by deepseek-r1 alias and all openrouter: prefixes)
export OPENROUTER_API_KEY=your_openrouter_key_here

# Local endpoints
export OLLAMA_HOST=http://localhost:11434  # default
export LOCAL_API_KEY=local                  # default
```
### Quick start — DeepSeek V4

```python
# DeepSeek V4 Flash (current recommended — replaces deepseek-chat)
from odot import OdotAgent
agent = OdotAgent(model="deepseek:deepseek-v4-flash")
result = agent.run_sync("Explain the Frobenius condition in 100 words.")
print(result)
```

```python
# DeepSeek V4 Pro (premium tier)
agent = OdotAgent(model="deepseek:deepseek-v4-pro")
result = agent.run_sync("Analyze the structural type of an LLM agent loop.")
```

```python
# DeepSeek R1 with reasoning via OpenRouter
agent = OdotAgent(model="openrouter:deepseek/deepseek-r1")
result = agent.run_sync("Analyze the structural type of an LLM agent loop.")
```

### Programmatic provider usage

```python
import asyncio
from odot import query_model, resolve_provider, DeepSeekProvider

# One-shot query — default model is deepseek-v4-flash
result = asyncio.run(query_model(
    "What is O_inf ouroboricity?",
    model="deepseek:deepseek-v4-flash",
    temperature=0.3,
))

# Direct provider instantiation
provider = DeepSeekProvider(model="deepseek-v4-flash")
result = asyncio.run(provider.query(
    "What is the Frobenius condition?",
    system="You are a structural type theorist.",
))

# Premium tier
provider_pro = DeepSeekProvider(model="deepseek-v4-pro")
result = asyncio.run(provider_pro.query(
    "Explain the lattice of ouroboricity tiers.",
))
```

### Retry and caching

All HTTP providers use exponential-backoff retry (5 attempts) with automatic `<think>...</think>` reasoning-block stripping (for DeepSeek-R1, Grok, etc.). Responses are cached at `~/.cache/odot/response_cache.db` for efficiency.

### Model details (from DeepSeek docs, fetched 2026-07-01)

| Feature | deepseek-v4-flash | deepseek-v4-pro |
|---|---|---|
| Context length | 1M tokens | 1M tokens |
| Max output | 384K tokens | 384K tokens |
| Thinking mode | Yes (default) | Yes (default) |
| JSON output | ✓ | ✓ |
| Tool calls | ✓ | ✓ |
| Pricing (cache hit) | $0.0028 / 1M input | $0.003625 / 1M input |
| Pricing (cache miss) | $0.14 / 1M input | $0.435 / 1M input |
| Pricing (output) | $0.28 / 1M output | $0.87 / 1M output |
| Concurrency limit | 2500 | 500 |

> **Deprecation notice:** `deepseek-chat` and `deepseek-reasoner` will be sunset on 2026/07/24 15:59 UTC. They currently map to non-thinking and thinking modes of `deepseek-v4-flash` respectively. See https://api-docs.deepseek.com/quick_start/pricing
