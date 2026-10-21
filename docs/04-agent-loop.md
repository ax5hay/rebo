# 04 · The agent loop

Code: `src/rebo/agent.py` (agent, tools, outcomes, validator) and `service.py` (`App.ask`,
`_context_block`, `_load_history`). Framework: **Pydantic AI 2.58** with `OpenRouterModel`.

## 1. Shape

```python
agent = Agent(
    OpenRouterModel("anthropic/claude-sonnet-5.5", provider=OpenRouterProvider(api_key=..., app_title="rebo")),
    deps_type=Deps,
    output_type=[ToolOutput(Report, name="present_report"),
                 ToolOutput(Clarify, name="ask_clarifying_question"),
                 ToolOutput(Reply, name="reply")],
    instructions=INSTRUCTIONS,                       # static, generic, cached
    model_settings=OpenRouterModelSettings(max_tokens=4096,
        openrouter_cache_instructions=True, openrouter_cache_tool_definitions=True),
    retries=2,
)
@agent.instructions  def database_context(ctx)   # dialect + every table with its row count (same every turn)
@agent.tool          search_schema / describe_table / search_values / find_join_path / search_knowledge / run_sql
@agent.output_validator def validate(ctx, output) # runs the final SQL; ModelRetry on failure
```

- **No `temperature`.** OpenRouter lists no `temperature` / `top_p` / `top_k` support for the
  Claude 5.x models, so none are sent.
- **Prompt caching.** Instructions and tool definitions are marked cacheable, so repeat turns pay
  only for the new context. The prefix is byte-identical across turns and users (B-010): static
  `INSTRUCTIONS`, then the dialect and the sorted table list, which change only on bootstrap; the
  date and the user's role and id are in the per-turn context block. `anthropic:` models use the
  1-hour TTL (`anthropic_cache_instructions="1h"`, tool definitions likewise); OpenRouter keeps the
  default 5 minutes. Offline test: `test_instructions_are_identical_across_turns_and_users`. Cache
  hits on a real API not yet measured (needs an LLM key).
- **Typed outcomes as tools.** The model ends a turn by calling exactly one of three output tools.
  Pydantic validates the arguments, and invalid arguments go back to the model automatically.

## 2. Dependencies passed to every tool (`Deps`)

```python
@dataclass
class Deps:
    app: App                 # store, target, catalog, index, knowledge, settings
    user: User               # id, role, team: visibility of knowledge depends on it
    trace: list[dict]        # one entry per tool call, returned to the caller as "trace"
    final: QueryResult|None  # rows of the accepted report (set by the validator)
    final_sql: str|None      # the SQL that actually ran (row cap applied)
    zero_row_retry: bool     # the 0-row nudge happens at most once
    probes: int              # run_sql count (hard stop at 12)
```

## 3. Tools: contracts the model sees

| Tool | Input | Returns | Notes |
|---|---|---|---|
| `search_schema(query)` | business words | ≤ 12 `{table, rows, about, column?, type?, column_about?, protected?}` | Hybrid FTS5 + vectors with RRF (doc 08) |
| `describe_table(table)` | name (case-insensitive) | `{table, rows, about, columns:[{name,type,pk?,protected?,null_rate,distinct,min,max,about,values:["Screening (12)", …]}], joins:["a.x = b.y (fk)", …]}` | Learned joins for this user are included. Unknown table → `ModelRetry` |
| `search_values(text)` | a literal | ≤ 15 `{value, table, column, freq}` | The value index: the exact stored spelling |
| `find_join_path(from_table, to_table)` | two tables | `["a.x = b.y (fk)", …]` or a hint to inspect columns | Dijkstra over fk 1.0 / learned 0.8 / inferred 1.5, max 5 hops |
| `search_knowledge(query)` | words | ≤ 6 `{id, kind, trust, title, question?, body?, sql?, confirmed_by?}` | Only items visible to this user |
| `run_sql(sql)` | one SELECT | `{columns, rows ≤20, more_rows, ms}` or `{error}` | Guarded; errors are returned as data, not raised |

The docstrings in `agent.py` are the tool descriptions the model reads, so keep them short and
behavioural.

## 4. The context block (first user message of each turn)

Built by `App._context_block(user, text)`, with no LLM call, so cheap and deterministic.
Shape below; the ids and counts are illustrative:

```xml
<turn>Today is 2026-10-21. The user is a user whose id in the host application is '42' (use it for 'my' / 'me' when a table stores that id).</turn>
<my_defaults>
period: last 30 days
</my_defaults>                                       ← only when the user set defaults (B-019)
<learned_knowledge>
{"id":"ex_3f…","kind":"example","trust":"verified","title":"Active surrogates in screening","question":"…","sql":"…","confirmed_by":4}
{"id":"te_91…","kind":"term","trust":"yours","title":"in intake","body":"active cases whose current stage is intake","sql":"gc_case.stage='intake' AND gc_case.active=1"}
</learned_knowledge>
<likely_tables>
gc_case (413 rows): gc_case is a case record table (one row per case …)
status (96 rows): Lookup table of workflow status labels …
</likely_tables>
<value_matches>
'Psychological Screening' is stored in status.status (9 rows)
'screening' is stored in gc_case.stage (61 rows)
</value_matches>
<request>Show me all active surrogates in Screening and list their current substage.</request>
```

On the live JMS test, a repeated question was answered with **zero tool calls** in 5 s, because
the user's confirmed example arrived in this block (doc 17).

## 5. Instructions (policy, not domain)

`INSTRUCTIONS` in `agent.py`, in summary:

1. Read learned knowledge first. *Verified* applies to everyone; *yours* was taught by this user.
   Adapt saved examples (change only literals, dates and grouping) and cite their ids in
   `used_knowledge`. Follow learned terms exactly.
2. Never guess tables or columns: use `search_schema` and `describe_table`.
3. Map every literal to a stored value (`search_values`, or the values shown by `describe_table`)
   with the exact spelling and case.
4. Get joins from `describe_table` / `find_join_path`. Watch for fan-out.
5. At most about 8 probes with `run_sql`.
6. Finish with exactly one outcome: `Report` (readable aliases, no protected columns, no LIMIT
   needed), `Clarify` (only when readings are plausible, not settled by knowledge, and give
   materially different results; **all** open questions bundled in one turn, at most 3, each with
   2–4 options from stored values; if one reading is clearly most likely, answer with it as an
   assumption; never re-ask what was answered), or `Reply`.
7. `assumptions` are in plain business language with no table or column names.
8. `follow_ups`: up to 3 drill-down questions, offered as one-click chips.
8. `learnable` holds only what the user explicitly stated; usually empty.
9. A correction from the user is the authority: revise, and put the general rule in `learnable`.

There is deliberately no JMS (or any domain) wording in the instructions. The previous agent
had JMS join rules hard-coded at `backend/app/services/reports_agent/loop.py:140-196`.

**Deterministic ask-gate** (`App._ask_gate`, B-006). Prompting alone over- or under-asks
(CIGAsk). So every `Question` also carries `option_sql`: the report SQL for its first two options.
Before a `Clarify` is shown, the service runs both through the guard and `same_result`. If, for
**every** question, the two readings return the same non-empty rows, the turn becomes a `Report`
built from question 1's first reading, with one assumption per question ("the readings X / Y give
the same result, so I did not ask"). Missing, unrunnable or rejected SQL, empty results or any
difference → the question is shown as before. `turn.usage.gate` records `asked` or `answered`;
`tools/eval_run.py` reports `clarify_rate` and `gate_answered`. Not yet measured on the eval sets
(needs an LLM key): the effect on the 18 JMS prompts' 6 clarifications is unknown.

**Clarification policy source.** AmbiSQL (SIGMOD'26 demo) and the expected-information-gain work
(arXiv 2507.06467): ask only when the candidate interpretations really diverge, as a multiple
choice. Otherwise answer and state the assumptions. BIRD-Interact shows interactive agents still
top out around 16–24%, so over-asking is not free.

## 6. Corrections and conversation memory

- A conversation's full Pydantic AI message history (including tool calls) is stored as JSON in
  `conversation.messages` (`ModelMessagesTypeAdapter`).
- `_load_history` keeps the last **4 user turns** (`_KEEP_RUNS`), cutting only at a user-prompt
  boundary so tool call/return pairs are never split.
- After **No, fix it**, the UI prefixes the user's next message with
  `"Correction to the previous report: "`. The model sees the previous report, its SQL and the
  correction in history, revises the report, and proposes the general rule as a `learnable`.

## 7. The output validator (`validate`)

For a `Report`:

1. `guard(sql, row_cap=row_limit+1)`. A `GuardError` → `ModelRetry("The report SQL was rejected: …")`.
2. `target.run(sql, max_rows=row_limit)`. A DB error → `ModelRetry("…failed in the database: …")`.
3. 0 rows and no nudge yet → `ModelRetry("returned 0 rows. Check each literal filter with
   search_values and each join with a count. If 0 rows is genuinely right, present it again and
   say why in the assumptions.")`. This catches the most common silent failure (a literal spelled
   differently from the stored value) without blocking real empty results.
4. Grain check (fan-out), once per turn: `entity_key` finds the first projected column that is the
   single-column primary key of a FROM/JOIN table (top-level SELECT with joins, no GROUP BY, no `*`;
   keys from `catalog.primary_keys`). If the fetched rows outnumber that column's distinct values →
   `ModelRetry("The rows repeat per <table> … aggregate or pick one row. If one row per joined record
   is intended, present it again and say so in the assumptions.")`. A second presentation is accepted.
   Why: a Haiku run returned one row per sub-stage instead of one per case, and the SQL ran fine
   (doc 20 §5). Not yet measured on the eval sets (needs an LLM key).
5. Otherwise store the rows in `deps.final` and accept.

**Second opinion** (`App._second_opinion`, B-013), after acceptance: a report whose provenance is
`new` and that rests on more than 2 assumptions is reviewed once by `models.fast` (question, SQL,
assumptions, first 10 rows) → `{ok, concern}`. A concern is appended as an assumption
"Check: …"; `turn.usage.review` = `ok` | `concern`. A failed review call never blocks the report.
Measured 2026-10-21b on the demo gold (Sonnet, `fixtures/demo_property/eval_results_sonnet_2026-10-21b.json`):
it reviewed 7 of 9 reports and raised 4 concerns; the one wrong report (gp-06) was among them, the
other 3 concerns were on correct reports (recall 1/1, precision 1/4). Content match 8/10 (7/10 before
all second-machine changes; not attributable to this change alone).

So **a report is never shown without having run successfully**. The rows the user sees are the
ones the validator fetched; no second execution happens.

## 8. Limits

| Limit | Value | Where |
|---|---|---|
| Model requests per turn | 40 | `UsageLimits(request_limit=40)` in `App.ask` |
| Tool calls per turn | 25 (`REBO_MAX_TOOL_CALLS`) | `UsageLimits(tool_calls_limit=…)` |
| Probes per turn | 12 (soft message at 13+) | `run_sql` |
| Output validation retries | 2 | `Agent(retries=2)` |
| Rows shown / probe rows | 500 / 20 | settings |

Exceeding a usage limit → `error_budget` message. Any other exception → `error_generic`, with
the stack trace logged.

## 9. Model choice

| Role | Default | Why |
|---|---|---|
| Agent | `anthropic/claude-sonnet-5.5` ($2/$10 per M tokens on OpenRouter, 1M context) | Best cost/quality for multi-step tool use |
| Bootstrap descriptions | `anthropic/claude-haiku-5.5` ($0.10/$0.50) | One structured call per table |

Both are environment settings (`REBO_MODEL`, `REBO_FAST_MODEL`). Any OpenRouter model with
tool calling works. Pydantic AI also supports Anthropic, Bedrock and OpenAI directly by swapping
the model class in `build_agent`.

### Back-translation in the second opinion (2026-10-21, B-049)

The reviewer's output now starts with `restated`: what the SQL returns, read from the SQL alone, and
only then `ok` / `concern` (GBV-SQL-style back-translation, doc 16 §5). `usage.review_restated` keeps
it for evals and traces; it is not shown. Demo gold, Sonnet agent + Haiku reviewer, concerns on gp-01…10:

| Run | Concerns on correct reports (false alarms) | Concerns on wrong reports | Wrong reports not flagged | Content match (12 cases) | Cost |
|---|---|---|---|---|---|
| before (2026-10-21b) | 3 | 1 | 0 | 8/10 (10 cases) | $0.236 |
| restate first, run 1 | 0 | 1 | 0 | 10/12 | $0.269 |
| restate first, run 2 | 1 | 1 | 2 | 9/12 | $0.225 |

False alarms fell (3 → 0 and 1) but one run missed two wrong reports: precision up, recall unsteady.
Two runs of a 10-case set cannot settle it; kept because false "Check:" notes on correct answers
erode trust and the cost is unchanged. Files: `eval_results_sonnet_backtranslate_{1,2}.json`.

### Execution agreement on unsure reports (2026-10-21, B-048)

Setting `checks.agreement` (env `REBO_AGREEMENT_CHECK`), **default off**. On the turns the second
opinion reviews (a new report with more than 2 assumptions), `App._agreement` runs alongside the review:

1. One structured call to the fast model (`candidate_agent`, tool `write_queries`) gets the question,
   the context block the agent saw, and the tables the report's SQL uses with their columns (protected
   columns left out), and returns up to 2 independently written queries, each with a plain reading.
2. Each runs through the guard and `_run_report_sql` (read-only, row cap); failures and truncated
   results are ignored.
3. Each result is compared with the report by content: `evals.columns_match` either way round (same
   rows; column order, names and extra columns ignored). Any agreement keeps the answer:
   `usage.agreement = agreed:n/m`.
4. If none agrees, one judge call (`judge_agent`, fast model) gets the question, the context and every
   query with its first 5 rows, and picks the report (`disagreed:report`, nothing added), a candidate
   (`disagreed:candidate`: a "Check: another reading gives a different result: …" note) or calls the
   question ambiguous (`disagreed:ambiguous`: a note naming both readings). The answer is never swapped:
   the person sees the other reading and can say "No, fix it".
5. Errors are logged and never block the answer (`usage.agreement = error`; `none` when no candidate
   ran). The extra tokens are in `usage.agreement_tokens` and `usage.agreement_cost_usd` (fast-model
   list price); they are not in the turn's main cost, like the reviewer's.

Sources: CHASE-SQL (ICLR'25), MaP-SQL (arXiv 2609.00834), "Two Surfaces of Ambiguity" (VLDB'26 AIDB);
doc 16 §5.

Measured 2026-10-21, demo gold (12 cases), Sonnet agent, Haiku candidates/judge/reviewer, flag on
(`eval_results_sonnet_agreement_on_{1,2}.json`) against the two back-translation runs with it off
(`eval_results_sonnet_backtranslate_{1,2}.json`). Gold verdicts for the wrong reports: gp-04 and gp-06.

| Run | Content match | Clarify | Checked turns | Agreed | Disagreed (report / candidate / ambiguous) | Wrong reports noted by the check | Notes on correct reports | Main cost | Check cost | Median s |
|---|---|---|---|---|---|---|---|---|---|---|
| off, run 1 | 10/12 | 1 | – | – | – | – | – | $0.269 | – | 12.4 |
| off, run 2 | 9/12 | 0 | – | – | – | – | – | $0.225 | – | 10.2 |
| on, run 1 | 10/12 | 0 | 10 | 7 | 1 / 1 / 1 | 1 of 2 (gp-06; gp-04 agreed 2/2) | 1 (gp-03, "open" vs "not closed") | $0.264 | $0.0067 | 14.1 |
| on, run 2 | 10/12 | 0 | 9 | 5 | 2 / 1 / 1 | 2 of 2 (gp-04 ambiguous, gp-06 candidate) | 0 | $0.287 | $0.0067 | 14.4 |

Reading: content match does not move (by design: the answer is never swapped). As an error signal,
disagreement noted 3 of the 4 wrong reports and put one note on a correct report whose question is
genuinely two-way; one wrong report (gp-04, run 1) had all 3 queries agree on the same misreading, the
known blind spot of self-agreement when the candidates see the same context. In these runs every wrong
report the check noted had already drawn a reviewer concern, so the check added no new catch over the
second opinion. Cost: about $0.0007 per checked turn (~2.5 % of the turn), +2 to 4 s median.
**Verdict: kept behind the flag, default off.** Two runs per arm on a 12-case set cannot show a gain; the
item asked for 3 runs each (not run: the third pair).

### Shape check: saved reports with the same query skeleton (2026-10-21, B-050, off by default)

`safety.skeleton` reduces a query to tables, columns, clauses and predicate shapes without values;
`skeleton_similarity` is a weighted Jaccard (tables 3, predicates 2, columns and clauses 1). With
`checks.shape` (`REBO_SHAPE_CHECK`), after a new report that used no saved knowledge, the validator
offers the agent, once, the two visible saved reports ≥ 45 % alike that were not in its context.

| Measurement | Result | File |
|---|---|---|
| Retrieval: the right saved report first, 77 JMS reports as the bank, 17 paraphrased questions with real agent drafts | skeleton of the draft **13/17** (MRR 0.863); question text 1/17 (0.173); fused 7/17 | `fixtures/jms_staging/skeleton_compare_2026-10-21.json` |
| Answers: 20 paraphrased JMS questions, bank of 77 saved, Sonnet, off vs on | off 3/17 $2.07; on 3/18 $2.53; fired 4×: adapted 1 (correct), kept 3 | `eval_results_shape_{off,on}_drafts20.json` |

The retrieval signal is strong but did not become better answers on this set (one run per arm, draft
questions are agent-written, not PO-validated), and it costs about 22 % more. Kept off. Where it could
pay: as a retrieval signal for a second pass that does not need an extra model turn (doc 16 §5).

### Metamorphic fan-out probe (2026-10-21, B-057)

A joined table that contributes no column (it appears only in its own ON condition) must not change
the result when the join becomes an `EXISTS` filter (`safety.fanout_probes`); if it does, the join
multiplied the rows and the validator asks once. Not applied when the query counts rows with
`COUNT(*)`/`COUNT(1)` (counting the joined rows on purpose). It needs no gold answer and costs one
extra read-only query, only when such a join exists. Mutation test (`tools/fanout_mutants.py`: every
gold report with each declared child table joined in, no LLM):

| Set | Real fan-out errors | Caught before | Caught with the probe | False alarms on correct gold |
|---|---|---|---|---|
| Demo, 12 reports | 10 | 2 (grain check) | **7** | 0/12 |
| JMS, 77 reports | 3,191 | 1,591 (50 %) | **1,836 (58 %)** | 1/77 |

Answers, demo gold, one run: 9/12 at $0.191 (previous run 11/12). The two changed cases are not the
probe's doing: one is variance (same request count), the other a false alarm of the older grain check
(a building id repeating per unit). Files: `fixtures/*/fanout_mutants_2026-10-21.json`,
`fixtures/demo_property/eval_results_sonnet_fanout_probe.json`.
