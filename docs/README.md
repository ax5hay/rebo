# Documentation

Read in order the first time. Each document names the code it describes (`file.py`, function names).

Start with **[AGENTS.md](../AGENTS.md)**: the direction and the rules that do not change. For running a
server, [OPERATIONS.md](../OPERATIONS.md); for changing the code, [CONTRIBUTING.md](../CONTRIBUTING.md).

| # | Document | Read it for |
|---|---|---|
| 01 | [Overview](01-overview.md) | What the bot is, goals and non-goals, how it differs from the two previous JMS bots |
| 02 | [Architecture](02-architecture.md) | Components, file map, one turn end to end, concurrency, state, technology choices |
| 03 | [Knowledge bootstrap](03-knowledge-bootstrap.md) | How the bot learns a database with no config: profiling, protected columns, value index, join inference, descriptions |
| 04 | [Agent loop](04-agent-loop.md) | Pydantic AI agent, tool contracts, context block, instructions, validator, limits, models |
| 05 | [Learning and trust](05-learning-and-trust.md) | Knowledge kinds, the trust state machine, every transition, provenance, scopes, poisoning defences, schema drift |
| 06 | [What the user sees](06-ux-copy.md) | Report card layout and every sentence the bot says, including "this only tunes the bot for you" |
| 07 | [SQL safety](07-sql-safety.md) | The five walls, the guard step by step, protected-column detection |
| 08 | [Retrieval](08-retrieval.md) | FTS5/BM25, local embeddings, RRF, knowledge ranking |
| 09 | [Data model](09-data-model.md) | Every table and column of `state.db` |
| 10 | [API, UI and MCP](10-api-and-ui.md) | Identity headers, every route with payloads, UI screens, MCP, JMS host adapter |
| 11 | [Evals and observability](11-evals-and-observability.md) | Eval format and evaluators, growing the eval set, offline tests, tracing |
| 12 | [Local DB and synthetic data](12-local-db-and-synthetic-data.md) | Staging snapshot (aws-vault), privacy filter, Docker MySQL, generator algorithm |
| 13 | [Operations](13-operations.md) | Settings, CLI, setup on a new PC, backups, deployment, security checklist |
| 14 | [Extraction ledger](14-extraction-ledger.md) | What was taken from the previous bots, what was dropped, and why |
| 15 | [Roadmap](15-roadmap.md) | Built vs designed, next steps in order of value, known gaps |
| 16 | [Research basis](16-research-basis.md) | Benchmarks, papers, product designs and versions behind each decision |
| 17 | [JMS as guinea pig](17-jms-guinea-pig.md) | Measured results on JMS, learning walkthrough, pilot script |
| 18 | [Production build](18-production-build.md) | **How to continue**: separate repo, the ~10-value config, JMS mocks, phased plan of small commits with gates |
| 19 | [Self-hosted alternatives](19-self-hosted-alternatives.md) | Open-source, Docker/local options for every component, verdicts, production and lean stacks |
| 20 | [LLM providers](20-llm-providers.md) | Claude / Gemini / LM Studio / OpenRouter, routing, prices, measured comparison |
| 21 | [Direction audit](21-direction-audit.md) | Every requirement vs what is built, with evidence and gaps |
| 22 | [Roles and user aids](22-roles-and-user-aids.md) | user / admin / owner permissions, every aid that exists, aids to add next |
| 23 | [Offline bundle](23-offline-bundle.md) | What leaves this machine, what was captured from JMS, setup with no JMS, made-up demo domain, checklist |
| 24 | [Runbook](24-runbook.md) | Backup/restore, upgrade, after target-DB migrations, rotating keys, moving to Postgres, knowledge export/import |
