# 20 · LLM providers, offline inference and routing

> Model IDs and prices below were checked on 2026-10-21 and change often. They are a starting point:
> re-check vendor pages and `openrouter.ai/api/v1/models` before changing defaults (`AGENTS.md` §4).

Code: `src/reportsbot/llm.py` (registry), `service.py` (`agent`, `fast_agent_model`,
`escalation_model`, routing in `ask`). Config: `models.*` and `lmstudio_url` in `reportsbot.yaml`.

## 1. Model strings

| String | Provider | Secret | Notes |
|---|---|---|---|
| `openrouter:anthropic/claude-sonnet-5.5` | OpenRouter (any model it lists) | `OPENROUTER_API_KEY` | prompt caching on (`openrouter_cache_instructions`, `…_tool_definitions`) |
| `anthropic:claude-sonnet-5-5` | Anthropic API | `ANTHROPIC_API_KEY` | `anthropic_cache_instructions`, `anthropic_cache_tool_definitions` |
| `google:gemini-3.8-flash` | Gemini API | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | implicit caching (needs a stable prefix ≥ 4,096 tokens) |
| `lmstudio:<id from GET /v1/models>` | LM Studio, local | none | OpenAI-compatible server at `lmstudio_url` |
| `openai:<model>` | OpenAI | `OPENAI_API_KEY` | — |
| `anthropic/claude-sonnet-5.5` (no prefix, has `/`) | OpenRouter | as above | backwards compatible |

Every model gets `max_tokens=4096`. **No `temperature`/`top_p`/`top_k` is sent**: Claude 5.5 models
return 400 for non-default sampling parameters, and Pydantic AI also strips them for these models.

## 2. The four roles

| Key | Used for | Default |
|---|---|---|
| `models.agent` | new questions | `openrouter:anthropic/claude-sonnet-5.5` |
| `models.fast` | turns that adapt a trusted saved example (routing below) and bootstrap descriptions | `openrouter:anthropic/claude-haiku-5.5` |
| `models.escalate` | one retry of a turn that failed on its first model (SQL never validated, budget exceeded, API error) | empty (off) |
| `models.fallback` | Pydantic AI `FallbackModel`: next provider when the API itself fails | `[]` |

**Routing (`App.ask`):**
1. Retrieve visible knowledge.
2. If the top results contain an `example` that is **verified or the user's own** and its question
   shares ≥ 60% of content words with this one (`_reuse_match`), run on `models.fast`. The turn only
   adapts saved SQL. Otherwise run on `models.agent`.
3. If the run raises (validator retries exhausted, `UsageLimitExceeded`, API error) and
   `models.escalate` is set, re-run once on the escalation model from a clean slate.
4. `turn.usage` records `model`, `route` (`reuse`/`new`) and `escalated`.

Tested offline: `test_trusted_saved_example_routes_to_fast_model_new_questions_to_agent_model`,
`test_failed_turn_escalates_once_to_the_stronger_model`.

## 3. Current models and prices (checked 2026-10-21)

| Model | API id | OpenRouter id | $/1M in · cache read · out | Notes |
|---|---|---|---|---|
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | `anthropic/claude-sonnet-5.5` | 2.00 · 0.10 · 10.00 | 1M context; no forced tool choice (Pydantic AI falls back to auto + retry) |
| Claude Haiku 5.5 | `claude-haiku-5-5` | `anthropic/claude-haiku-5.5` | 0.10 · 0.01 · 0.50 (prompts ≤ 100k) | above 100k: 0.50 · 0.05 · 2.50 |
| Claude Opus 5.5 | `claude-opus-5-5` | `anthropic/claude-opus-5.5` | 4.00 · 0.20 · 20.00 | offline jobs |
| Gemini 4 Argon | `gemini-4-argon` | `google/gemini-4-argon` | 2.00 · 0.10 · 10.00 → **doubles from 2026-12-01** | no explicit caching |
| Gemini 3.8 Flash | `gemini-3.8-flash` | `google/gemini-3.8-flash` | 0.75 · 0.075 · 3.75 → **doubles from 2027-01-01** (OpenRouter ~10% higher) | thinking default medium; "minimal" not allowed |
| Gemini 3.5 Flash-Lite | `gemini-3.5-flash-lite` | `google/gemini-3.5-flash-lite` | 0.30 · 0.03 · 2.50 | cheapest Gemini |

Batch APIs are 50% off for evals and offline jobs. Sources: ai.google.dev/gemini-api/docs/{models,pricing,caching},
platform.claude.com/docs/en/about-claude/{models/overview,pricing}, openrouter.ai/api/v1/models.

## 4. LM Studio (offline)

1. Install LM Studio ≥ 0.4.26 (or headless: `lms daemon up`). Download a model that shows the
   **tool-use badge** in LM Studio's catalog (native tool calling). Otherwise LM Studio falls back to
   prompt-injected tool calls, with variable results.
2. Start the server: `lms server start` (default `http://localhost:1234/v1`). JIT loading is on by
   default, and idle models unload after 60 minutes.
3. `curl http://localhost:1234/v1/models`, then copy the model id.
4. `reportsbot.yaml`:
   ```yaml
   models: {agent: "lmstudio:<id>", fast: "lmstudio:<id>"}
   lmstudio_url: http://127.0.0.1:1234/v1
   embeddings: true          # fastembed is local too, so fully offline
   ```
5. Fully offline also means: `uv sync` once while online (Python packages and the fastembed model
   are cached), the MySQL container, no OpenRouter key.

Suggested local models (Q4, approximate VRAM; tool-use badge in LM Studio):

| Model | VRAM | Use |
|---|---|---|
| Qwen3.8-27B | ~20–24 GB | default local agent |
| Qwen3.6-35B-A3B (MoE) | ~24 GB | faster |
| gpt-oss-20b | ~16 GB | smaller GPUs |
| gpt-oss-120b | ~66–80 GB | server class |
| Arctic-Text2SQL-R1-7B / OmniSQL-7B (Apache-2.0) | ~6–8 GB | SQL-specialised; tool calling not verified |

Verified: the `lmstudio:` path drives a full agent turn over the OpenAI-compatible protocol
(`tests/test_llm.py::test_lmstudio_wire_protocol_end_to_end`, against a stand-in server).
**Not verified:** a real LM Studio install, since none is on this machine. Expect to tune
`limits.tool_calls` and possibly use `PromptedOutput` for weaker local models (doc 18 P1.10).

## 5. Measured on the 18 JMS prompts (local synthetic DB, empty knowledge, 2026-10-21)

Results files: `fixtures/jms_staging/eval_results_*.json` (per case: kind, rows, seconds, model,
route, escalation, tokens, cost estimated from the prices above).

| Setup | Reports | Clarify | Errors | Escalated | Median s | Cost, 18 questions |
|---|---|---|---|---|---|---|
| Sonnet 5.5 (run 1, `eval_results_2026-10-21.json`) | 12 | 6 | 0 | — | 14.5 | not recorded (≈$0.15/question from tokens) |
| Sonnet 5.5 (run 2, `eval_results_sonnet.json`) | 12 | 6 | 0 | 0 | 14.8 | **$2.02** |
| Haiku 5.5 → Sonnet escalation (`eval_results_haiku_cascade.json`) | 11 (+1 plain answer) | 6 | 0 | 2 | 13.7 | **$0.36** |
| Gemini 3.8 Flash via OpenRouter (`eval_results_gemini38flash.json`) | 3 | 5 | **10** | 0 (off) | **91.7** | $0.86 (successful turns only) |

What this shows:
- **The Haiku cascade is 5.7× cheaper** at the same answer rate. But on validated-01 Haiku returned
  one row per sub-stage (fan-out, 15 rows) where Sonnet returned one row per case. The SQL ran, so
  the validator could not catch it. Hence Sonnet stays the default agent, Haiku handles reuse turns,
  and doc 18 P1.7 (grain check) targets exactly this.
- **Run-to-run variance is real.** Sonnet answered validated-16 with 55 rows in run 1 and 5 rows in
  run 2 (different readings of "pending approval"). Confirmed knowledge removes this for repeat
  questions, and the gold set (P1.1) is needed to grade accuracy.
- **Gemini 3.8 Flash does not work with this loop as-is.** 8 of its 10 errors were the 25-tool-call
  budget (it explores far more per question with default medium thinking); 2 were failed
  validations. Its median latency was 6× Claude's. This is a configuration problem as much as a
  model one: the prompt and budgets were tuned implicitly on Claude. **Next commit** (doc 18
  P1.10): per-model profile (thinking `low` for Gemini 3.x, a higher tool budget, parallel tool calls)
  and re-measure. Until then, use Gemini as `models.fallback`, or behind `models.escalate`.
- Direct `google:` (Gemini API) builds offline but was not run live (no Gemini key on this machine).

## 6. Recommended setups

| Goal | agent | fast | escalate | fallback |
|---|---|---|---|---|
| Accuracy first (default) | Sonnet 5.5 | Haiku 5.5 | — | `google:gemini-3.8-flash` |
| Cost first | Haiku 5.5 | Haiku 5.5 | Sonnet 5.5 | — |
| Offline | `lmstudio:<Qwen3.8-27B>` | same | — | — |
| Gemini experiment | `google:gemini-3.8-flash` (after P1.10) | `google:gemini-3.5-flash-lite` | Sonnet 5.5 | — |
