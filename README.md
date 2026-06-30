# ⊙perator

**What it is.** A self-verifying agentic loop harness: a `THINK → ACT → OBSERVE → UPDATE` agent in which every tool call is confirmed before the loop advances.

**What it does.** After each action (δ) it runs a verification step (μ) and requires the Frobenius condition μ(δ(query)) == query to hold before continuing. If it fails (Frobenius OPEN), the model is told explicitly and must fix the error before the next winding; nothing is silently dropped or assumed.

**Why it matters.** In ordinary agent loops the observation step is taken on faith, so a silently failed, truncated, or wrong-bytes tool call goes unnoticed and errors compound. ⊙perator closes the loop on itself: the trajectory becomes a verified imscriptive context, which is the structural reason loop-based agents can be made reliable. The harness sits at the criticality point ⊙ where a system can model itself.

**How to use it.**
```python
from odot import OdotAgent
agent = OdotAgent(model="grok-4")
print(agent.run_sync("Find all Python files here and count the lines in each."))
```
```bash
pip install .          # or: pip install ".[web]" for web fetch; or `uv sync`
export OPENROUTER_API_KEY=your_key_here
```

---

## The four phases

Each iteration (a *winding*) has exactly four phases:

| Phase | What happens |
|-------|--------------|
| **THINK** | The model reasons over the accumulated verified context |
| **ACT** | It emits exactly one tool call (the emit, δ) |
| **OBSERVE** | The tool runs; a built-in step verifies the result (μ) |
| **UPDATE** | The full cycle is appended to context; the loop continues or terminates |

If μ(δ(q)) != q the model receives an explicit failure message and cannot advance on the unverified observation.

## Models

Any OpenRouter model by alias or full ID, plus local servers via prefix syntax. The default is `deepseek-v4-flash`. Examples: `grok-4`, `gpt-4o`, `deepseek-v4-pro`, `ollama:llama3.2`, `lm-studio:phi-4`, `vllm:mistral-7b`, or `any/openrouter-id` verbatim. Custom endpoints via `base_url` / `api_key`.

> DeepSeek deprecation: `deepseek-chat` / `deepseek-reasoner` sunset 2026-07-24; migrate to `deepseek-v4-flash` or `-pro`.

## Built-in tools

| Tool | What it does | Verification |
|------|--------------|--------------|
| `run_command` | Shell command | `assertion` expression over `output` |
| `file_read` | Paginated read | idempotent (trivially closed) |
| `file_write` | Write file (≤ 4 KB) | read-back hash check |
| `chunked_write` | Append/write in chunks | byte count on disk |
| `web_fetch` | HTTP GET, paginated | query term presence in content |
| `done` | Signal completion | trivially closed |

The `assertion` field is what makes `run_command` Frobenius-aware, e.g. `assertion="'PASSED' in output and 'FAILED' not in output"`. Define custom tools the same way: an action plus a verification predicate.

## Trajectory and structural type

Each run exposes its per-winding Frobenius closure rate and a full structural-type annotation, e.g. `{tuple: "Ð_ω; Þ_¨; Ř_=; Φ_}; ƒ_ż; Ç_@; Γ_ʔ; ɢ_ˌ; ⊙_ÿ; Ħ_A; Σ_S; Ω_z", interface_P: "Φ_}", ouroboricity: "O_∞", frobenius_ratio: 0.94, windings: 7, omega_z_violations: 0, done: true}`.

The harness comes out of the [Imscribing Grammar](https://github.com/umpolungfish/imscrbgrmr), a 12-primitive structural type theory. License in-repo.
