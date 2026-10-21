# AGENTS.md: direction and working rules for anyone (human or AI agent) building this bot

Read this before changing anything. It states what the product is, the rules that do not change,
and how to work. Details live in `docs/` (start at `docs/README.md`).

## 0. When the user says "continue" (or gives no other instruction)

Do this without asking questions. The user expects work to resume and keep going.

1. **Orient.** Read `HANDOFF.md` (state, measured facts, gotchas, working style), then this file,
   then `BACKLOG.md`.
2. **Prepare the machine.** Run:
   ```
   uv sync --all-extras --frozen
   uv run python tools/doctor.py
   ```
   Doctor restores git history from `reportsbot.git.bundle` on first run, creates `reportsbot.yaml`
   and `.env` from their examples, starts the local MySQL and fills it (if Docker exists), builds the
   demo database, bootstraps both catalogs, runs the tests, and prints **NEXT**: the first backlog
   item this machine can do. If it reports failing tests, fixing them is the first task.
3. **Clean up an interrupted session.** If `git status` shows uncommitted work:
   - inspect it, then finish and commit it if it matches a `[~]` backlog item;
   - otherwise stash it with a descriptive message and note it in `HANDOFF.md`.
4. **Do the NEXT item.** Mark it `[~]` in `BACKLOG.md`, then:
   - follow its *do* steps;
   - research first wherever it says so (§4);
   - write tests and update the docs it names;
   - make small commits (§3, docs/18 §0);
   - run `uv run pytest` before every commit.

   If the change affects answers and an LLM key exists, measure with `tools/eval_run.py` and commit
   the results file. Without a key, write `eval pending: needs llm` on the item.
5. **Close the item.** Mark it `[x]` with `result: <date>, <commits>, <numbers>`. Add a line to the
   `HANDOFF.md` session log and update anything in `HANDOFF.md` §1–§4 that changed. Commit.
6. **Keep going** with the next item (re-run `uv run python tools/doctor.py --check --no-tests` to pick
   it). Stop only when:
   - the remaining items need resources this machine lacks (`docker`, `llm`, `lmstudio`, `node`,
     `browser`), or need a human; or
   - you are running out of context or budget.

   Before stopping, the tree must be committed and `HANDOFF.md` must say exactly where to resume.
7. **Never:**
   - push to a remote or publish anything unless the user asks;
   - put API keys in files;
   - add domain meaning to configuration;
   - start an item marked `human`;
   - contact JMS (it is unreachable and out of scope).

   If an item turns out to need a human decision, mark it `[!]` with the question and move on.

Optional resources unlock more items: LLM API keys in `.env` (`OPENROUTER_API_KEY` is enough),
Docker, LM Studio running on port 1234, Node, browser automation. Absence is not an error: do the
items that fit.

## 1. What this is

A **self-contained reports bot** for any SQL database. People ask for reports in plain words; the
bot answers with one read-only query, the rows, and how it read the question. It **learns** from the
people who use it, not from configuration.

- **The database is the only input about the domain.** The bot reads its structure, statistics and
  stored values (`reportsbot bootstrap`). Everything else about meaning comes from people in the chat:
  confirmed reports, corrections, definitions, joins.
- **Configuration is ~10–20 lines** (`reportsbot.yaml`): which database, which models, limits, who
  may do what. **Never** add domain meaning to configuration (no semantic YAML, concept registries,
  glossaries or per-customer prompt rules). If a change needs domain knowledge, it belongs in
  *learned knowledge* (people teach it; admins can also add or edit it directly).
- **JMS is only the test database.** JMS data (structure snapshot, statistics, captured contract,
  gold reports) lives in `fixtures/`, the JMS chat contract in `src/reportsbot/adapters/jms.py`, and a
  stand-in for JMS in `mocks/jms/`. No JMS names in `src/` outside the adapter. Once this folder
  leaves the original machine there is **no access to JMS, its APIs or its databases**: everything
  runs locally against the replicated structure with synthetic data, or against any other database
  (see the made-up `fixtures/demo_property/`).

## 2. Who can do what (enforced in code; `docs/22-roles-and-user-aids.md`)

| Role | Can |
|---|---|
| **user** | ask; confirm or reject answers, in buttons or in their own words; undo their feedback; teach things for themselves; edit/withdraw their own unshared knowledge; request fixes they cannot make |
| **admin** | everything a user can, plus add, edit, share, withdraw and undo **any** learned knowledge; review the queue; resolve requests; export/import knowledge as YAML |
| **owner** | everything an admin can, plus change the configuration (validated, audited, rollback). Editing `reportsbot.yaml` by hand on the server is also an owner action |

Personal first, shared by evidence: what one user teaches affects only them until three people
independently agree and an admin approves, or an admin adds it directly. Nothing is ever deleted;
everything has a history and can be undone.

## 3. Rules that do not change

1. **Read-only, always.** The SQL guard (sqlglot syntax tree), read-only DB user and session,
   timeouts and protected-column detection stay. No feature may write to the reported database.
2. **Every answer is executed before it is shown,** and says where it came from and how the
   question was read.
3. **Minimal config.** New settings need a default that keeps current behaviour, must not carry
   domain meaning, and the total stays ≤ 20 lines in the example file.
4. **Self-contained.** No runtime dependency on JMS or on any service that cannot run locally,
   except the LLM APIs (and LM Studio for offline inference).
5. **Small commits.** One behaviour change per commit, with its test and doc change; behaviour that
   changes answers comes with an eval results file (`tools/eval_run.py`). Rules: `docs/18-production-build.md` §0.
6. **Measure, don't assume.** Accuracy, turns and cost claims cite a results file in `fixtures/*/eval_results_*.json`.
7. **Say what is not verified.** In docs and commit messages, mark anything not run as not run.

## 4. Research protocol: tool suggestions are inputs, not decisions

`docs/19-self-hosted-alternatives.md` and `docs/20-llm-providers.md` list tools, models and prices
**as researched on 2026-10-21**. They are **suggestions**. Before adopting any library, service or
model, the implementing agent must research it again itself:

1. **Re-verify** the current version, release date, licence (watch for AGPL/BUSL/ELv2/"restricted"
   changes), maintenance status (archived? acquired? last release?) and security advisories, on the
   primary source (GitHub, PyPI, vendor docs). Do not trust the dates in these docs.
2. **Search for alternatives** that appeared since, including self-hostable / Docker / local options.
   Prefer boring, widely used, permissively licensed components that run in one container or in-process.
3. **Check fit with the direction:** does it need domain configuration? (reject); does it add a
   runtime service? (justify); can it be swapped behind one config key with today's behaviour as default?
4. **Prototype behind a flag, measure** with `tools/eval_run.py` on `fixtures/demo_property/gold.jsonl`
   and the JMS sets, and compare cost, latency and accuracy against the current component.
5. **Record the decision** (date, sources, numbers, verdict) in the relevant doc, in the same commit.

The same applies to model choice: model IDs and prices change monthly. Re-check
`openrouter.ai/api/v1/models` and the vendor pricing pages before changing defaults.

## 5. How to work in this repo

```bash
uv sync --all-extras && uv run pytest              # offline, ~10 s, no network, no LLM
docker compose up -d db && uv run --extra synth python tools/synth/synth.py   # local JMS-shaped DB
uv run python fixtures/demo_property/build.py      # made-up second domain (SQLite)
uv run reportsbot bootstrap --describe && uv run reportsbot serve
uv run python tools/eval_run.py <cases.jsonl> <results.json> [limit]
uv run python tools/export_bundle.py               # the checked zip for another machine
```

Where things are: `docs/02-architecture.md` (file map), `docs/18-production-build.md` (what to build
next, commit by commit), `docs/21-direction-audit.md` (requirements vs reality).
