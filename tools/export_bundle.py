"""Make the zip that leaves this machine, and prove it is safe to send.

    uv run python tools/export_bundle.py                      # ../reportsbot-<date>.zip
    uv run python tools/export_bundle.py --with-models        # + the local embedding model (offline use)

Includes the whole reports-bot folder except local state and secrets. Fails (exit 1, no zip) when any
included file contains a secret-looking value or a real database host; warns about email addresses
that are not on example domains. Writes BUNDLE_MANIFEST.json (files, sha256, git commit, checks) into
the zip. See docs/23-offline-bundle.md for what is inside and why.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".venv", "data", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".git", "models"}
EXCLUDE_FILES = {".env", "reportsbot.yaml"}
EXCLUDE_SUFFIXES = {".db", ".db-wal", ".db-shm", ".pyc", ".zip"}
SECRETS = {
    "OpenRouter / OpenAI key": re.compile(r"sk-(or-v1-)?[A-Za-z0-9_-]{24,}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "AWS access key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    "real RDS endpoint": re.compile(r"[a-z0-9-]+\.[a-z0-9]{8,}\.[a-z]{2}-[a-z]+-\d\.rds\.amazonaws\.com"),
    "database URL with password": re.compile(r"mysql\+pymysql://(?!reports_ro:reports_ro@|root:root@|user:pass@)[^:\s/]+:[^@\s]{6,}@"),
}
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
EMAIL_OK = re.compile(r"(example\.(com|org|net)|anthropic\.com)$")


def included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    root_level = len(rel.parts) == 1  # .env / reportsbot.yaml are local only at the top; fixtures may have their own
    return not (set(rel.parts[:-1]) & EXCLUDE_DIRS or rel.parts[0] in EXCLUDE_DIRS
                or (root_level and path.name in EXCLUDE_FILES) or path.suffix in EXCLUDE_SUFFIXES
                or (root_level and path.name in ("BUNDLE_MANIFEST.json", "reportsbot.git.bundle")))


def scan(files: list[Path]) -> tuple[list[str], list[str]]:
    problems, warnings = [], []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, rx in SECRETS.items():
            for m in rx.finditer(text):
                problems.append(f"{f.relative_to(ROOT)}: {name}: {m.group(0)[:12]}…")
        emails = {m.group(0) for m in EMAIL.finditer(text) if not EMAIL_OK.search(m.group(1))}
        if emails:
            warnings.append(f"{f.relative_to(ROOT)}: {len(emails)} non-example email address(es), e.g. {sorted(emails)[0]}")
    return problems, warnings


def fastembed_cache() -> Path | None:
    for c in (os.environ.get("FASTEMBED_CACHE_PATH"), Path(os.environ.get("TEMP", "/tmp")) / "fastembed_cache"):
        if c and Path(c).is_dir() and any(Path(c).iterdir()):
            return Path(c)
    return None


def git_history_bundle() -> Path | None:
    """Committed history of just this folder as a git bundle (subtree split when it lives inside a
    larger repository). Uncommitted changes are not in it; the manifest records them."""
    def git(*a: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    top = git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    prefix = os.path.relpath(ROOT, top.stdout.strip()).replace("\\", "/")
    out = ROOT.parent / ".reportsbot.git.bundle.tmp"
    if prefix in (".", ""):
        r = git("bundle", "create", str(out), "HEAD")
    else:
        branch = "reportsbot-export"
        git("branch", "-D", branch)
        split = git("subtree", "split", "-P", prefix, "-b", branch, "HEAD", cwd=Path(top.stdout.strip()))
        if split.returncode != 0:
            print("WARN  history not included: git subtree split failed:", split.stderr[-200:])
            return None
        r = git("bundle", "create", str(out), branch)
        git("branch", "-D", branch)
    return out if r.returncode == 0 and out.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT.parent / f"reportsbot-{dt.date.today().isoformat()}.zip")
    ap.add_argument("--with-models", action="store_true", help="include the fastembed model cache as models/fastembed")
    ap.add_argument("--no-history", action="store_true", help="leave out reportsbot.git.bundle (the commit history)")
    args = ap.parse_args()

    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and included(p))
    problems, warnings = scan(files)
    for w in warnings:
        print("WARN ", w)
    if problems:
        for p in problems:
            print("BLOCK", p)
        print(f"{len(problems)} problem(s): no zip written.")
        return 1
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain", "--", "."], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    manifest = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "git_commit": commit,
                "uncommitted_changes": dirty, "checks": {"secrets": "passed", "warnings": warnings},
                "files": []}
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            data = f.read_bytes()
            arc = Path("reportsbot") / f.relative_to(ROOT)
            z.writestr(str(arc).replace("\\", "/"), data)
            manifest["files"].append({"path": str(f.relative_to(ROOT)).replace("\\", "/"),
                                      "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        if args.with_models:
            cache = fastembed_cache()
            if not cache:
                print("No fastembed cache found: run `uv run reportsbot bootstrap` once with embeddings on first.")
                return 1
            for f in sorted(cache.rglob("*")):
                if f.is_file():
                    z.write(f, str(Path("reportsbot/models/fastembed") / f.relative_to(cache)).replace("\\", "/"))
            manifest["models"] = "models/fastembed (set FASTEMBED_CACHE_PATH or keep it in place: found automatically)"
        if not args.no_history:
            hist = git_history_bundle()
            if hist:
                z.write(hist, "reportsbot/reportsbot.git.bundle")
                manifest["history"] = "reportsbot.git.bundle (committed history of this folder; tools/doctor.py restores it)"
                hist.unlink()
            else:
                manifest["history"] = "not included (not a git checkout)"
        z.writestr("reportsbot/BUNDLE_MANIFEST.json", json.dumps(manifest, indent=1))
    size = args.out.stat().st_size / 1e6
    print(json.dumps({"zip": str(args.out), "files": len(files), "mb": round(size, 1), "git_commit": commit,
                      "uncommitted_changes": dirty, "warnings": len(warnings)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
