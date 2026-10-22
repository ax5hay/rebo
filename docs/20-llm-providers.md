# 20 · LLM providers, offline inference and routing

> Model IDs and prices below were checked on 2026-10-21 and change often. They are a starting point:
> re-check vendor pages and `openrouter.ai/api/v1/models` before changing defaults (`AGENTS.md` §4).

Code: `src/rebo/llm.py` (registry), `service.py` (`agent`, `fast_agent_model`,
`escalation_model`, routing in `ask`). Config: `models.*` and `lmstudio_url` in `rebo.yaml`.

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

**Measured 2026-10-21b (B-008), demo DB, Sonnet + Haiku via OpenRouter:** first question "List the
open maintenance requests with priority urgent": 3 requests, $0.038. The same question after the
person confirmed it (route `direct`): 0 requests, $0. The same report with another value ("priority
high", route `params`): 1 Haiku request, $0.00013, with the right filter (`priority = 'high'`, 8
rows instead of 4), about 290× cheaper than a new question.

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
4. `rebo.yaml`:
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
| gpt-oss-120b (OpenAI, Apache-2.0) | ~66–80 GB | default local agent, server class |
| gpt-oss-20b (OpenAI, Apache-2.0) | ~16 GB | smaller GPUs |
| a recent Gemma (Google), Mistral or Llama (Meta) instruct model with tool use | varies | alternatives; measure before use |

Chinese-origin models (DeepSeek, Qwen, GLM, MiMo, Kimi, BAAI, ...) are excluded by policy (2026-10-22).

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

### 4.2 Measured: Gemini free tier, staggered (B-045 variant, 2026-10-21b)

Google AI Studio free tier, called directly (`google:`), with PatientModel waiting out HTTP 429s.
`gemini-3.8-flash`: 5 requests/minute and **20/day**; one turn needs about 10, so the day's quota ran
out after the first questions and the rest failed (not a model result). `gemini-3.5-flash-lite` has
its own free quota and completed the demo gold set:

| Model (free tier) | Content match | Reports / clarify / errors | Median s | Cost | File |
|---|---|---|---|---|---|
| gemini-3.5-flash-lite | **7/10** | 9 / 1 / 0 | 83 (mostly waiting on the per-minute limit; unthrottled ones 5–11 s) | $0 | `fixtures/demo_property/eval_results_gemini35flashlite_freetier.json` |
| Sonnet 5.5 (paid), same day | 8/10 | 9 / 1 / 0 | 10.4 | $0.24 | `eval_results_sonnet_2026-10-21b.json` |

Flash-lite was right on gp-06 where Sonnet was wrong, and wrong on gp-03 (9 buildings counted where
gold has 12) and gp-05 (asked a clarifying question). For trying ReBo without paying, flash-lite on
the free tier is usable; for daily use the per-minute limit makes answers slow.

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
| Haiku 5.5 → Sonnet escalation, second machine (`eval_results_haiku_cascade_2026-10-21b.json`) | 9 (+2 plain answers) | 7 | 0 | 0 | 18.0 | **$0.14** |
| Gemini 3.8 Flash via OpenRouter **with the B-012 profile** (`eval_results_gemini_profile.json`) | 13 | 3 | 2 (both HTTP 504 from OpenRouter) | 0 (off) | 104.3 | $1.82 |

Gemini profile (B-012: thinking `low`, 1.6× tool budget, parallel tool calls), 2026-10-21b: errors
fell from 10/18 (tool budget exhausted) to 2/18, both upstream timeouts (HTTP 504 from OpenRouter),
none from the budget; 13 reports vs 3. Still the slowest (median 104 s, up to 344 s) and not cheap
($1.82 vs Sonnet's $2.68 for the same 18). Data and code also changed since the first Gemini run.

Second-machine Haiku cascade (2026-10-21b): $0.14 for 18 prompts (about 20× cheaper than Sonnet's
$2.68, 2.6× cheaper than the first cascade run's $0.36), no escalation needed. validated-01, the
earlier fan-out case (15 rows, one per sub-stage), now returns 3 rows, the same as Sonnet; whether
the grain check (B-005) fired or the new data avoided it is not recorded (retries are not logged).
Haiku asks more (7 clarifications vs Sonnet's 5) and answers two prompts in words instead of a
report. Row counts agree with Sonnet on 8 of the 9 prompts both answered with a report.

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
| Cost first (small schemas, §5b) | GPT-6 Luna Pro + `decide: Sonnet 5.5` | Haiku 5.5 | — | — |
| Offline | `lmstudio:<gpt-oss-120b>` | same | — | — |
| Gemini experiment | `google:gemini-3.8-flash` (after P1.10) | `google:gemini-3.5-flash-lite` | Sonnet 5.5 | — |

## Caching the growing turn (2026-10-21, B-052)

Before, only the instructions and tool definitions were cached; each of a turn's 4–5 requests re-sent
the tool results so far at full price. `llm.build_one` now also caches the latest message for Claude
models (`openrouter_cache_messages`, `anthropic_cache_messages="5m"`; not for Gemini, where OpenRouter
keeps only the last breakpoint).

| Set, Sonnet 5.5 | Cache-read share of input | Cost | Answers |
|---|---|---|---|
| JMS 18 prompts, before (2026-10-21b) | 17 % | $2.68 | 13 reports, 5 clarifications |
| JMS 18 prompts, after | **72 %** | **$1.22** (2.2× less) | 13 reports, 4 clarifications |
| Demo gold, before (two runs) | 53 %, 64 % | $0.269, $0.225 | 10/12, 9/12 |
| Demo gold, after | 62 % | $0.254 | 10/12 |

Files: `fixtures/jms_staging/eval_results_sonnet_cachemsgs.json`, `fixtures/demo_property/eval_results_sonnet_cachemsgs.json`.

## Verifier-gated cascade (2026-10-21, B-053)

With `models.escalate` set, a turn now also goes to the escalation model when a check had to step in
on the cheaper model's answer (a SQL trap or grain problem caught by the validator, or a second-opinion
concern), not only when the cheaper model fails. The discarded run's tokens stay in `usage.before` and
are counted in the cost. Demo gold, one run each:

| Setup | Content match | Cost | Escalated |
|---|---|---|---|
| Sonnet 5.5 (default, with message caching) | 10/12 | $0.254 | – |
| Haiku 5.5 alone | 7/12 | $0.017 | – |
| Haiku → Sonnet when in doubt | 8/12 | $0.106 | 2 (trap, review) |

The doubt signals flagged 2 of Haiku's 5 wrong answers, so the cascade is 2.4× cheaper but 2 cases
worse than Sonnet. **Sonnet stays the default**; the cascade remains the cost option. A better doubt
signal (B-048 agreement, used as the trigger) is the next thing to try. Files:
`fixtures/demo_property/eval_results_haiku_only.json`, `eval_results_haiku_doubt_cascade.json`.

## 5b. Cheaper agent models and doubt-gated decide (2026-10-21)

Re-checked `openrouter.ai/api/v1/models` on 2026-10-21 for tool-capable models priced like Haiku.
Demo gold (12), one run each, everything else unchanged:

| Agent model (input/output $ per 1M) | Content match | Cost | File |
|---|---|---|---|
| Sonnet 5.5 ($2/$10), recent runs | 9–11/12 | $0.19–0.25 | `eval_results_sonnet_compact.json`, `_fanout_probe.json` |
| GPT-6 Luna Pro ($0.10/$0.50) | 9/12 | $0.030 | `eval_results_gpt-6-luna.json` |
| Haiku 5.5 ($0.10/$0.50) | 7/12 | $0.017 | `eval_results_haiku_only.json` |

On the JMS schema (6 validated prompts) GPT-6 Luna Pro **asked a clarifying question on 5 of 6**
where Sonnet answered (reasonable questions, but too many), $0.053 vs $0.373
(`jms_staging/eval_results_luna6.json`).

Two ways of adding Sonnet back only where it matters, `models.decide` (off by default):

| Setup | Demo | JMS 6 | Verdict |
|---|---|---|---|
| Haiku explores, Sonnet always writes the answer from its lookups | 8/12, $0.243 | – | rejected: Sonnet anchored on the cheap draft (same misses as Haiku) and cost as much as Sonnet alone |
| Luna answers; Sonnet decides only on doubt (wants to ask, trap, grain, review concern) from Luna's lookups | 9/12, **$0.028** (no doubt fired) | 5 reports + 1 question, **$0.395** (5 decides) | kept as an option; **not the default** |

**Decision: Sonnet stays the agent.** On a small schema the cheap tier is 7–9× cheaper at similar
accuracy; on the realistic schema the cheap model is unsure on most questions, so the decide step runs
anyway and saves nothing, while each wrong report costs trust. The bill is cut where accuracy is not
at stake instead: answer cache, saved-report reuse, parameter fill, re-runs, schedules and the "Read
as" switches cost $0 per question (doc 27 §2); message caching cut JMS cost 2.2× (B-052) and compact
tool results 25 % of input (B-054). Settings for a small, simple schema:
`models: {agent: openrouter:openai/gpt-6-luna-pro, decide: openrouter:anthropic/claude-sonnet-5.5}`.

## 5c. Other non-Claude models on Orbitra (2026-10-22): Claude stays

Only models from non-Chinese labs are considered (policy, 2026-10-22). Orbitra gold (48 questions,
221-table database), scored with `tools/rescore.py` ("same numbers" counts right answers presented
differently):

| Agent | Same numbers | Cost for 48 | Median s / question | Model requests / question | Note |
|---|---|---|---|---|---|
| **Claude Sonnet 5.5 (default)** | **44/48** | $1.11 | **11** | 3.0 | |
| xAI Grok 4.3 ($1.25/$2.50) | 40/48 | $0.62 | 18 | 3.5 | cheaper, less accurate, slower |
| Google Gemini 3.8 Flash ($0.83/$4.13) | stopped | $0.41 for 16 questions | ~100 | 7.3 | 3 errors in 16; 41k tokens a question |
| Mistral Large 4 ($1.36/$4.18) | stopped | $0.42 for ~20 | ~45 | 4.1 | stopped at the user's request |

Why the others are slower: they need more round-trips (each re-sends the turn), ReBo caches the growing
turn only for Claude (OpenRouter keeps one cache breakpoint for other providers, so every request
re-reads 15–40k prompt tokens), some reason silently before answering, and provider throughput varies.

Light model (`tools/fast_model_check.py`: second opinion on 30 correct reports and 30 wrong twins, and
24 value fills from saved reports):

| Light model | Wrong caught | False alarms | Values filled | Cost |
|---|---|---|---|---|
| **Claude Haiku 5.5 (default)** | 30/30 | 9/30 | 19/24 | $0.018 |
| OpenAI GPT-6 Luna | 30/30 | 15/30 | 18/24 | $0.010 |
| Google Gemma 4 31B | 28/30 | 2/30 | 19/24 | $0.012 |

**Decision (the user, 2026-10-22): Claude for both, Sonnet 5.5 agent and Haiku 5.5 light model.**
Other providers remain usable through the same model strings; nothing in the bot depends on Claude.
