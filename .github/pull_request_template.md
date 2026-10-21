## What and why

<!-- One behaviour change. Why it is needed. -->

## How it was checked

- [ ] `uv run pytest -q` green (and with `REBO_TEST_STATE_URL` when the state store changed)
- [ ] `uvx ruff check src tests tools mocks --select F,E9,B --ignore E501,B008,B905`
- [ ] Changes answers? Eval results file committed (`tools/eval_run.py`), numbers below
- [ ] Docs updated; anything not run is marked as not run
- [ ] No domain meaning added to configuration (AGENTS.md §1)
