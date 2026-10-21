"""Prepare and check this machine, then say which backlog item to do next.

    uv sync --all-extras --frozen          # first (installs everything; doctor does not install packages)
    uv run python tools/doctor.py          # prepare + check + next item  (safe to run any time)
    uv run python tools/doctor.py --check  # report only, change nothing

Prepares (idempotent):
- git history from rebo.git.bundle;
- rebo.yaml and .env from their examples;
- the local MySQL container and its synthetic rows;
- the demo SQLite database;
- the bot's catalogs for both databases.

Then reports what this machine can do (docker, LLM keys, LM Studio, node), runs the offline tests and
prints the first BACKLOG.md item whose needs are met. Writes data/capabilities.json.
Part of the "continue" protocol in AGENTS.md §0.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
LOG: list[str] = []


def say(msg: str) -> None:
    LOG.append(msg)
    print(msg, flush=True)


def run(cmd: list[str], *, env: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def env_file() -> dict[str, str]:
    out = {}
    p = ROOT / ".env"
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if v.strip():
                    out[k.strip()] = v.strip()
    return out


def git_setup(check: bool) -> dict:
    inside = run(["git", "rev-parse", "--is-inside-work-tree"]).stdout.strip() == "true"
    bundle = ROOT / "rebo.git.bundle"
    if not inside and not check:
        run(["git", "init", "-b", "main"])
        if not run(["git", "config", "user.email"]).stdout.strip():
            run(["git", "config", "user.email", "rebo-agent@localhost"])
            run(["git", "config", "user.name", "rebo agent"])
        if bundle.is_file():
            heads = run(["git", "bundle", "list-heads", str(bundle)]).stdout.split()
            ref = heads[1] if len(heads) > 1 else "HEAD"
            r = run(["git", "fetch", str(bundle), ref])
            run(["git", "reset", "--mixed", "FETCH_HEAD"])
            say(f"git: restored history from {bundle.name}" + ("" if r.returncode == 0 else f" (fetch: {r.stderr[:200]})"))
        else:
            run(["git", "add", "-A"])
            run(["git", "commit", "-q", "-m", "import rebo bundle"])
            say("git: new repository with one import commit (no history bundle found)")
        inside = True
    dirty = run(["git", "status", "--porcelain", "--", "."]).stdout.strip().splitlines() if inside else []
    head = run(["git", "log", "--oneline", "-1"]).stdout.strip() if inside else None
    return {"repo": inside, "head": head, "uncommitted": dirty[:20]}


def ensure_files(check: bool) -> None:
    for target, example in (("rebo.yaml", "rebo.example.yaml"), (".env", ".env.example")):
        if not (ROOT / target).exists() and not check:
            shutil.copyfile(ROOT / example, ROOT / target)
            say(f"created {target} from {example}")
    if "REBO_DATABASE_URL" in env_file():
        say("WARNING: .env sets REBO_DATABASE_URL, which overrides `database:` in every YAML (docs/23 §4). "
            "Keep .env for API keys only.")


def capabilities() -> dict:
    keys = {**env_file(), **os.environ}
    caps = {"offline": True, "human": False, "browser": False}
    caps["openrouter"] = bool(keys.get("OPENROUTER_API_KEY") or keys.get("REBO_OPENROUTER_API_KEY"))
    caps["anthropic"] = bool(keys.get("ANTHROPIC_API_KEY"))
    caps["gemini"] = bool(keys.get("GEMINI_API_KEY") or keys.get("GOOGLE_API_KEY"))
    caps["openai"] = bool(keys.get("OPENAI_API_KEY"))
    caps["llm"] = any(caps[k] for k in ("openrouter", "anthropic", "gemini", "openai"))
    caps["docker"] = shutil.which("docker") is not None and run(["docker", "info"], timeout=30).returncode == 0
    caps["node"] = shutil.which("node") is not None and shutil.which("npm") is not None
    url = "http://127.0.0.1:1234/v1"
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from rebo.settings import Settings  # noqa: E402
        url = Settings().lmstudio_url
    except Exception:
        pass
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/models", timeout=2) as r:
            caps["lmstudio"] = r.status == 200
    except Exception:
        caps["lmstudio"] = False
    for mod in ("fastembed", "faker", "fastmcp"):
        caps[f"extra_{mod}"] = importlib.util.find_spec(mod) is not None
    return caps


def local_mysql(check: bool, caps: dict) -> dict:
    if not caps["docker"]:
        return {"status": "skipped (no docker): JMS-shaped tests unavailable; the demo domain still works"}
    if not check:
        run(["docker", "compose", "up", "-d", "db"], timeout=600)
        for _ in range(60):
            if run(["docker", "compose", "exec", "-T", "db", "mysqladmin", "ping", "-uroot", "-proot"]).returncode == 0:
                break
            time.sleep(3)
    q = lambda sql: run(["docker", "compose", "exec", "-T", "db", "mysql", "-uroot", "-proot", "-N", "jms", "-e", sql])
    tables = q("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='jms'").stdout.strip()
    rows = q("SELECT COUNT(*) FROM gc_case").stdout.strip()
    if tables.isdigit() and int(tables) > 0 and rows == "0" and not check:
        say("synthetic data: generating (about 5 minutes) ...")
        r = run([sys.executable, "tools/synth/synth.py"], timeout=3600)
        say("synthetic data: " + (r.stdout.strip().splitlines()[-1] if r.returncode == 0 else f"FAILED {r.stderr[-300:]}"))
        rows = q("SELECT COUNT(*) FROM gc_case").stdout.strip()
    return {"tables": tables, "gc_case_rows": rows}


def demo_db(check: bool) -> dict:
    db = ROOT / "fixtures" / "demo_property" / "greenleaf.db"
    if not db.exists() and not check:
        spec = importlib.util.spec_from_file_location("demo_build", ROOT / "fixtures" / "demo_property" / "build.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build(db)
        say("demo database built")
    return {"exists": db.exists()}


def catalog_ready(state_db: Path) -> bool:
    if not state_db.exists():
        return False
    try:
        with sqlite3.connect(state_db) as c:
            return c.execute("SELECT COUNT(*) FROM cat_table").fetchone()[0] > 0
    except sqlite3.Error:
        return False


def bootstrap(check: bool, caps: dict) -> dict:
    out = {}
    describe = ["--describe"] if caps["llm"] else []
    targets = [("demo_property", ROOT / "data" / "demo_property" / "state.db",
                {"REBO_CONFIG": "fixtures/demo_property/rebo.yaml"})]
    if caps["docker"]:
        targets.append(("jms_local", ROOT / "data" / "state.db", {"REBO_CONFIG": "rebo.yaml"}))
    for name, state, env in targets:
        if not catalog_ready(state) and not check:
            say(f"bootstrap {name}{' with descriptions' if describe else ''} ...")
            r = run([sys.executable, "-m", "rebo.cli", "bootstrap", *describe], env=env, timeout=3600)
            line = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("{")), r.stderr[-300:])
            say(f"bootstrap {name}: {line}")
        out[name] = "ready" if catalog_ready(state) else "not bootstrapped"
    return out


def tests() -> dict:
    r = run([sys.executable, "-m", "pytest", "-q"], timeout=1800)
    last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    return {"passed": r.returncode == 0, "summary": last}


_ITEM = re.compile(r"^### \[( |~|x|!)\] (B-\d+) · (.+)$")


def next_item(caps: dict) -> dict | None:
    lines = (ROOT / "BACKLOG.md").read_text(encoding="utf-8").splitlines()
    items, cur = [], None
    for line in lines:
        m = _ITEM.match(line)
        if m:
            cur = {"state": m.group(1), "id": m.group(2), "title": m.group(3), "needs": []}
            items.append(cur)
        elif cur and line.startswith("needs:"):
            cur["needs"] = [n.strip() for n in line.split(":", 1)[1].split(",") if n.strip()]
    for it in items:
        if it["state"] == "~":
            return {**it, "why": "in progress: resume it"}
    for it in items:
        if it["state"] == " " and all(caps.get(n, False) for n in it["needs"]):
            return {**it, "why": "first todo item whose needs are met"}
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--no-docker", action="store_true", help="act as if docker were unavailable")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = {"git": git_setup(args.check)}
    ensure_files(args.check)
    caps = capabilities()
    if args.no_docker:
        caps["docker"] = False
    report["capabilities"] = caps
    if not all(caps[f"extra_{m}"] for m in ("fastembed", "faker", "fastmcp")):
        say("WARNING: optional extras missing: run `uv sync --all-extras --frozen`")
    report["mysql"] = local_mysql(args.check, caps)
    report["demo"] = demo_db(args.check)
    report["bootstrap"] = bootstrap(args.check, caps)
    if not args.no_tests:
        report["tests"] = tests()
    report["next"] = next_item(caps)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "capabilities.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n=== doctor summary ===")
    print(json.dumps(report, indent=2))
    if report["next"]:
        print(f"\nNEXT: {report['next']['id']} · {report['next']['title']} ({report['next']['why']})")
    else:
        print("\nNEXT: nothing doable here; every remaining item needs a resource this machine lacks (see BACKLOG.md).")
    return 0 if report.get("tests", {}).get("passed", True) else 1


if __name__ == "__main__":
    sys.exit(main())
