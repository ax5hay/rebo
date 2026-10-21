# 23 · What leaves this machine (the offline bundle)

After the zip leaves the original machine there is **no access to JMS**: no JMS APIs, no staging or
production RDS, no aws-vault, no VPN, no orchid code. Everything the bot needs was captured
beforehand and is inside the bundle. The only network access needed afterwards is to the LLM APIs
(OpenRouter / Anthropic / Gemini), and none at all with LM Studio plus a pre-fetched embedding model.

## 1. Make the bundle

```bash
uv run python tools/export_bundle.py                 # ../reportsbot-YYYY-MM-DD.zip
uv run python tools/export_bundle.py --with-models   # + models/fastembed (≈130 MB) for fully offline use
```

The tool includes the whole folder except `.venv/`, `data/` (the bot's memory on this machine),
`models/`, `.env`, the local `reportsbot.yaml`, generated `*.db` files and caches.

**It refuses to write the zip** if any file contains:
- an API key (OpenRouter/OpenAI, Anthropic, Google),
- an AWS access key, a private key or a JWT,
- a real RDS endpoint,
- a database URL carrying a real password.

It warns about email addresses not on example domains. It writes `BUNDLE_MANIFEST.json`: the
sha256 of every file, the git commit, and whether there were uncommitted changes. Tested in
`tests/test_bundle.py`.

To carry the git history as well, see doc 18 §1 (`git subtree split`).

## 2. Everything captured from JMS (and nothing else is needed)

| Need after leaving | Captured as | How it was made | Contains real data? |
|---|---|---|---|
| The database structure | `fixtures/jms_staging/schema.sql` (207 tables, 440 FKs, indexes) | `tools/snapshot/snapshot.py` against staging, read-only | No |
| Realistic data | `fixtures/jms_staging/profile.json` (row counts, null rates, ranges, lengths; categorical value lists filtered for personal data; 51 measured undeclared references) → `tools/synth/synth.py` generates rows | same | Aggregates and business vocabulary only (doc 12 §1) |
| The database engine | `docker-compose.yml` → `mysql:8.0.44`, same charset, collation and sql_mode as staging | `manifest.json` | No |
| How JMS talks to the bot | `fixtures/jms_contract/` (JSON Schemas generated from the real models; JWT claims; endpoint; WebSocket message; save-to-Builder rules) | from the orchid-ai-intake-bot code | No |
| A stand-in for JMS | `mocks/jms/server.py` (token, admin directory, custom-report save + Builder grammar, re-run) + `src/reportsbot/adapters/jms.py` | written to the captured contract | No |
| Acceptance questions | `fixtures/jms_staging/eval.jsonl` (18 PO-validated prompts) | JMS-6723 corpus | No |
| Human-built reports (gold SQL) | `fixtures/jms_staging/gold_custom_reports.jsonl` (79; 12 with real questions, `prompt_quality`) | `tools/jms_capture/capture_gold.py`, screened for personal literals | SQL text only |
| Measured baselines | `fixtures/jms_staging/eval_results_*.json` | `tools/eval_run.py` | Synthetic rows only |

Deliberately **not** captured:
- Real rows: privacy, and they would go stale anyway.
- The old bots' YAML semantic layers (concept registry, vocabulary, schema digest). The bot must
  learn meaning; shipping those would be the "semantic dump" this product avoids.
- Credentials of any kind.

If you know you will need something else from JMS later, capture it **before** the zip leaves:
- **More report gold:** have a PO write one real question per report in
  `gold_custom_reports.jsonl` (`question`, `prompt_quality: question`).
- **A fresh structure:** re-run `tools/snapshot/snapshot.py` (doc 12).

## 3. Set up on the new machine

```bash
unzip reportsbot-*.zip && cd reportsbot
git init -b main && git add -A && git commit -m "import"     # own repo (or use the subtree history)
uv sync --all-extras                                         # needs PyPI once
uv run pytest                                                # all offline
docker compose up -d db                                      # JMS-shaped MySQL, structure only
uv run --extra synth python tools/synth/synth.py             # synthetic rows
cp reportsbot.example.yaml reportsbot.yaml                   # ~10–20 lines; edit models
cp .env.example .env                                         # API keys only
uv run reportsbot bootstrap --describe && uv run reportsbot serve
```

Fully offline:
1. Build the bundle with `--with-models`. The retriever finds `models/fastembed` automatically, or
   set `FASTEMBED_CACHE_PATH`.
2. Point `models.agent` and `models.fast` at `lmstudio:<id>` (doc 20 §4).
3. Install the Python packages from a local wheelhouse:
   - **On the connected machine:** `uv export --frozen > requirements.txt` then `pip download -r requirements.txt -d wheels`.
   - **On the offline machine:** `uv pip install --no-index --find-links wheels -r requirements.txt`.
4. Use a pre-pulled `mysql:8.0.44` image: `docker save` on the connected machine, then `docker load` on the offline one.

## 4. A made-up database for a new domain (no JMS at all)

`fixtures/demo_property/` is the template:
- `build.py` makes a deterministic SQLite database for a made-up property-management company.
- `reportsbot.yaml` is 5 lines: the database URL and a separate memory folder.
- `gold.jsonl` holds 10 questions with verified SQL.

```bash
uv run python fixtures/demo_property/build.py
REPORTSBOT_CONFIG=fixtures/demo_property/reportsbot.yaml uv run reportsbot bootstrap --describe
REPORTSBOT_CONFIG=fixtures/demo_property/reportsbot.yaml uv run reportsbot serve --port 8081
uv run python tools/eval_run.py fixtures/demo_property/gold.jsonl fixtures/demo_property/eval_results_<name>.json
```

Measured on 2026-10-21 (Sonnet 5.5, empty knowledge, results in
`fixtures/demo_property/eval_results_sonnet.json`):
- 9 reports and 1 justified clarification ("late payment" is not a stored field).
- **7/10 match the gold answer's content** and **9/10 match the gold row count**.
- $0.27 for all 10.

The two remaining misses are presentational: a technician column labelled differently, and a
tenant id shown where a name was wanted.

To add another domain:
1. Copy the folder.
2. Write a builder (or point `database:` at any real read-only database).
3. Write ten gold questions with SQL.
4. Bootstrap, evaluate, compare.

**Keep each domain's `state_dir` separate.** Learned knowledge belongs to one database.

**Configuration precedence trap:** a `REPORTSBOT_DATABASE_URL` line in `.env` overrides `database:`
in any YAML. Keep `.env` for secrets only (`.env.example` says so). This trap was hit once on
2026-10-21.

## 5. Checklist before the zip leaves

- [ ] `uv run pytest` green; `git status` clean (the manifest records uncommitted changes).
- [ ] `uv run python tools/export_bundle.py` passes with 0 blocks; any warnings reviewed.
- [ ] Gold questions written by a PO if accuracy on JMS must be measured later (§2).
- [ ] Decide `--with-models` (offline embeddings) and a wheelhouse (offline install) if needed.
- [ ] No `.env`, `reportsbot.yaml`, `data/` or `*.db` in the zip (the tool excludes them; check the manifest).
