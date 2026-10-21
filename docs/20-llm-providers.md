# 20 · LLM providers, offline inference and routing

> Model IDs and prices below were checked on 2026-10-21 and change often. They are a starting point:
> re-check vendor pages and `openrouter.ai/api/v1/models` before changing defaults (`AGENTS.md` §4).

Code: `src/reportsbot/llm.py` (registry), `service.py` (`agent`, `fast_agent_model`,
`escalation_model`, routing in `ask`). Config: `models.*` and `lmstudio_url` in `reportsbot.yaml`.

## 1. Model strings

| String | Provider | Secret | Notes |
|---|---|---|---|
| `openrouter:anthropic/claude-sonnet-5.5` | OpenRouter (any model it lists) | `OPENROUTER_API_KEY` | prompt caching on (`openrouter_cache_instructions`, `…_tool_definitions`) |
| `anthropic:claude-sonnet-5-5` | Anthropic API | `ANTHROPIC_API_KEY` | `anthropic_cache_instructions`, `anthropic_cache_tool_definitions`, both `"1h"` |
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
1. **Direct, no model.** The user's own confirmed example whose question is the same text (case,
   spacing and end punctuation ignored) is re-run through the guard (`_direct_answer`).
   **Cache, no model.** Otherwise, on the first turn of a conversation, an exact answer cache
   (B-031) keyed by the normalised question, the user and team, the knowledge version (latest
   history event) and the catalog version returns the earlier SQL re-run fresh (route `cache`).
   Never semantic; follow-ups inside a conversation are never cached; a "wrong" verdict removes
   the entry; any knowledge change or re-bootstrap invalidates every entry.
2. Retrieve visible knowledge.
3. If the top results contain an `example` that is **verified or the user's own** and its question
   shares ≥ 60% of content words with this one (`_reuse_match`):
   - **Params, one fast call.** If the example has a template (B-008), one `fill_parameters` call on
     `models.fast` decides whether only values changed and returns them; they are put back as
     syntax-tree literals and run (`_param_answer`). Not the same report, a failing query or 0 rows →
     next step.
   - Otherwise the agent runs on `models.fast`; the turn only adapts saved SQL.
4. Anything else runs the agent on `models.agent`.
5. If the run raises (validator retries exhausted, `UsageLimitExceeded`, API error) and
   `models.escalate` is set, re-run once on the escalation model from a clean slate.
6. `turn.usage` records `model`, `route` (`direct`/`cache`/`params`/`reuse`/`new`, and `rerun` for
   "Re-run with today's data") and `escalated`.

Tested offline: `test_trusted_saved_example_routes_to_fast_model_new_questions_to_agent_model`,
`test_failed_turn_escalates_once_to_the_stronger_model`,
`test_exact_repeat_of_own_confirmed_question_makes_no_model_request`,
`test_saved_report_with_new_values_is_filled_in_without_the_agent`. The cost saving of the direct
and params routes has not been measured with a real model yet (needs an LLM key).

### 2.1 Per-model profiles (`llm.PROFILES`, B-012)

A profile says how one model family is driven; the first entry whose key is a substring of the
model name applies, and models with no entry keep the defaults (today's behaviour):

| Field | Effect | Default |
|---|---|---|
| `thinking` | unified Pydantic AI `thinking` setting (Gemini → `thinking_level`, OpenRouter → `reasoning`) | provider default |
| `tool_call_factor` | multiplies `limits.tool_calls` for turns on that model (`App._limits`) | 1.0 |
| `parallel_tool_calls` | model setting | provider default |
| `output` | `tool` (outcome tools) or `prompted` (`PromptedOutput`: JSON in text, for local models whose tool calls fail) | `tool` |

Entries today: `gemini-3` → thinking `low`, 1.6× tool budget (25 → 40), parallel tool calls. Why:
Gemini 3.8 Flash ran out of tool budget on 10 of 18 prompts (§5). Research, 2026-10-21: the installed
Pydantic AI 2.58.0 (PyPI, released 2026-10-20) documents the unified `thinking` field as supported
by Google and OpenRouter, and maps `low` to Gemini's `LOW` thinking level (source:
`pydantic_ai/settings.py`, `models/google.py`). No new dependency. The Gemini values are a first
guess: **not measured** (needs an LLM key; target file `eval_results_gemini_profile.json`).
No LM Studio entry is set: which local models need `prompted` is unknown until one is run.

### 2.2 Cost cap per turn and rate limit (B-032)

`limits.cost_per_turn_usd` (0 = off) stops a turn that would cost more, in **list prices** (`llm.PRICES`,
equal to `openrouter.ai/api/v1/models` on 2026-10-21). Pydantic AI's `UsageLimits(cost_limit=…)`
prices responses with genai-prices (0.1.13, 2026-10-15, MIT), which on 2026-10-21 covered every
configured model but disagreed for some: for 1M input + 0.1M output, Sonnet 5.5 $3.00 (same),
Haiku 5.5 $0.75 vs $0.15 list (5× high), Gemini 3.8 Flash $1.125 vs $1.2375 (9% low). So
`llm.turn_limits` scales the cap by genai-prices ÷ list price for that model; a model genai-prices
does not know is capped by token limits from the list (80% of the cap for input, 20% for output);
`lmstudio:` (no price) is not capped. Exceeding it ends the turn with the usual budget message.
`limits.per_user_per_minute` (0 = off) limits questions per person in a sliding minute (in-process;
HTTP 429). Not measured against a real API (needs a key).

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
A real LM Studio install was run on the second machine (§4.1). Expect to tune
`limits.tool_calls` and possibly use `PromptedOutput` for weaker local models (doc 18 P1.10).

### 4.1 Measured: LM Studio with google/gemma-4-e2b (B-044, 2026-10-21)

LM Studio on this Mac (arm64, 24 GB) with `google/gemma-4-e2b` loaded (a ~2B model), demo gold set,
`models.agent` and `models.fast` both `lmstudio:google/gemma-4-e2b`, empty knowledge:

| Run | Reports | Errors | Content match (gold) | Median s/question | File |
|---|---|---|---|---|---|
| default profile (2 output retries) | 7 + 1 plain answer | 2 (SQL that never parsed: retries exhausted) | **1/10** | 77 | `fixtures/demo_property/eval_results_lmstudio.json` |
| `gemma-4` profile, 4 output retries, the 2 failed questions only | 2 | 0 | 0/2 | 44 | `eval_results_lmstudio_retries4_gp03_gp09.json` |
| Sonnet 5.5 for comparison | 9 + 1 clarification | 0 | 7/10 | 8.9 | `eval_results_sonnet.json` |

gp-01 in the full run was served by the exact answer cache (B-031) from a one-question trial run
just before (same model, same question), hence 0 s. Tool calling works over the OpenAI-compatible
protocol; the model finds the right tables but gets grain and filters wrong (e.g. counting units
instead of rent collected, building ids instead of names). Profile `gemma-4` → `output_retries: 4`
turns parse failures into answers a person can correct; it does not improve accuracy. Verdict: a 2B
local model is usable for trying the bot offline, not for answers people rely on. A larger
tool-calling model (§4 table) was not available here.

## 5. Measured on the 18 JMS prompts (local synthetic DB, empty knowledge, 2026-10-21)

Results files: `fixtures/jms_staging/eval_results_*.json` (per case: kind, rows, seconds, model,
route, escalation, tokens, cost estimated from the prices above).

| Setup | Reports | Clarify | Errors | Escalated | Median s | Cost, 18 questions |
|---|---|---|---|---|---|---|
| Sonnet 5.5 (run 1, `eval_results_2026-10-21.json`) | 12 | 6 | 0 | — | 14.5 | not recorded (≈$0.15/question from tokens) |
| Sonnet 5.5 (run 2, `eval_results_sonnet.json`) | 12 | 6 | 0 | 0 | 14.8 | **$2.02** |
| Haiku 5.5 → Sonnet escalation (`eval_results_haiku_cascade.json`) | 11 (+1 plain answer) | 6 | 0 | 2 | 13.7 | **$0.36** |
| Gemini 3.8 Flash via OpenRouter (`eval_results_gemini38flash.json`) | 3 | 5 | **10** | 0 (off) | **91.7** | $0.86 (successful turns only) |
| Sonnet 5.5, second machine, all of B-001…B-044 (`eval_results_sonnet_2026-10-21b.json`) | 13 | 5 | 0 | 0 | 19.3 | **$2.68** |

Second-machine Sonnet run (2026-10-21b): new synthetic data with ordered dates (B-042), a
re-bootstrapped catalogue with Haiku descriptions, and every change since (grain check, ask-gate,
cache-stable prefix, second opinion, …). Prompt caching works: every turn read 3k–27k cached
tokens (B-010). The ask-gate checked all 5 clarifications and converted none (the readings really
differed). The second opinion ran on 13 reports and raised a concern on 9: on inspection they are
specific (an assumption contradicting the SQL, statuses that do not mean "awaiting approval", a
join through `gc_id` for sperm donors); whether they are right is not graded (no gold for these
prompts). It is the main reason cost rose from $2.02 to $2.68 and the median from 14.8 s to 19.3 s
(not separated in this run). Data, catalogue and code all changed, so the difference to run 2 is not
attributable to one change.

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
