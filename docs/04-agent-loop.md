# 04 · The agent loop

Code: `src/reportsbot/agent.py` (agent, tools, outcomes, validator) and `service.py` (`App.ask`,
`_context_block`, `_load_history`). Framework: **Pydantic AI 2.58** with `OpenRouterModel`.

## 1. Shape

```python
agent = Agent(
    OpenRouterModel("anthropic/claude-sonnet-5.5", provider=OpenRouterProvider(api_key=..., app_title="reportsbot")),
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
Before/after on the demo gold not yet measured (needs an LLM key).

So **a report is never shown without having run successfully**. The rows the user sees are the
ones the validator fetched; no second execution happens.

## 8. Limits

| Limit | Value | Where |
|---|---|---|
| Model requests per turn | 40 | `UsageLimits(request_limit=40)` in `App.ask` |
| Tool calls per turn | 25 (`REPORTSBOT_MAX_TOOL_CALLS`) | `UsageLimits(tool_calls_limit=…)` |
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

Both are environment settings (`REPORTSBOT_MODEL`, `REPORTSBOT_FAST_MODEL`). Any OpenRouter model with
tool calling works. Pydantic AI also supports Anthropic, Bedrock and OpenAI directly by swapping
the model class in `build_agent`.
