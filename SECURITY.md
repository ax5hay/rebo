# Security

ReBo reads databases that hold business data. Report a vulnerability privately to the maintainer,
Akshay Bajpai (https://www.akshaybajpai.com, project: https://ghosthub.in), or through a private
GitHub security advisory on this repository. Please do not open public issues for security matters.

What the code guarantees and where it is enforced:

- **Read-only.** Every query passes the sqlglot guard (`src/rebo/safety.py`), runs on a read-only
  session with a timeout, and should use a read-only database user. Nothing writes to the reported
  database.
- **Protected columns** (secrets, personal identifiers) are detected at bootstrap and can never be
  selected or shown.
- **Identity** comes from a trusted gateway (`auth.mode: headers`) or signed JWTs. Behind the login
  proxy, client-sent `X-User-*` headers are ignored (`deploy/auth/README.md`). Never expose the bot
  without one of these in front.
- **Rendering.** Text from people and models is rendered as Markdown with raw HTML disabled
  (`web/src/md.tsx`); links open in a new tab without an opener.
- **Secrets** live only in the environment (`.env`, never committed, never in the Docker build
  context). `tools/export_bundle.py --check-only` and the pre-commit hook refuse files that contain keys.
- **Traces** leave prompts and rows out unless `REBO_TRACE_CONTENT=true`.
- **Dependencies** are audited in CI (`pip-audit`, `npm audit`) and updated by Dependabot.
