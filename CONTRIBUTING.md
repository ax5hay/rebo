# Contributing

Read `AGENTS.md` first: what the product is, the rules that do not change, and the "continue"
protocol. This file is the practical checklist for a change.

## Setup and checks

```bash
uv sync --all-extras                                   # dependencies
uv run pytest -q                                       # offline tests: no network, no LLM, ~10 s
uvx ruff check src tests tools mocks --select F,E9,B --ignore E501,B008,B905
uvx pre-commit install                                 # optional: runs ruff + the secret scan on commit
```

CI (`.github/workflows/ci.yml`) runs the same three commands on every push and pull request.

## Evals (behaviour that changes answers)

```bash
uv run python tools/eval_run.py <cases.jsonl> <results.json> [limit]
```

Needs an LLM key in `.env`. Case sets: `fixtures/demo_property/gold.jsonl` and the JMS sets in
`fixtures/jms_staging/`. Commit the results file with the change; accuracy, turns and cost claims
cite it (`AGENTS.md` §3.6). Without a key, write `eval pending: needs llm` on the backlog item.

## The bundle (moving the folder to another machine)

```bash
uv run python tools/export_bundle.py --check-only      # secret scan only, writes nothing
uv run python tools/export_bundle.py                   # ../rebo-<date>.zip
```

The export fails (exit 1, no zip) on anything that looks like a secret or a real database host.
See `docs/23-offline-bundle.md`.

## Commit rules (docs/18 §0)

| Rule | Why |
|---|---|
| One behaviour change per commit; tests and docs for that change in the same commit | `git log -p <file>` explains every line; reverts are surgical |
| Commit message: `type(scope): what` + a body saying *why* and how it was measured | Conventional Commits; the body is the changelog |
| `uv run pytest` green before committing (offline, no network) | The suite runs on a SQLite fixture and mocked LLM/JMS, so it is fast and deterministic |
| Behaviour that changes answers: run `tools/eval_run.py` and commit the results file | Accuracy and cost are tracked like code |
| No domain words in `src/` (`tests/test_no_domain_words.py`) | Keeps the product generic; JMS lives in fixtures, mocks and adapters only |
| Secrets never in files; config only in `rebo.yaml` | One place to look; nothing leaks into git |
| Mark anything not run as not run | Docs and commit messages must not claim unverified results |

Type prefixes: `feat` (behaviour), `fix`, `perf` (cost/latency), `eval` (eval sets/results), `docs`,
`test`, `build` (packaging/CI), `chore`. Scope: `rebo`.

## Research protocol: tool suggestions are inputs, not decisions (AGENTS.md §4)

Docs 19 and 20 list tools, models and prices as researched on 2026-10-21. Before adopting any
library, service or model:

1. **Re-verify** the current version, release date, licence (watch for AGPL/BUSL/ELv2/"restricted"
   changes), maintenance status and security advisories on the primary source.
2. **Search for alternatives** that appeared since, including self-hostable / local options. Prefer
   boring, widely used, permissively licensed components that run in one container or in-process.
3. **Check fit:** no domain configuration; justify any new runtime service; swappable behind one
   config key with today's behaviour as the default.
4. **Prototype behind a flag and measure** with `tools/eval_run.py` against the current component.
5. **Record the decision** (date, sources, numbers, verdict) in the relevant doc, in the same commit.
