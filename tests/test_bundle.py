import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_bundle", ROOT / "tools" / "export_bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)

# Fake secrets are assembled at runtime so this file itself passes the bundle scan.
_J = "".join
FAKE = "\n".join([
    _J(["key=sk-or-v1-", "a" * 40]),
    _J(["AKIA", "B" * 16]),
    _J(["prod-db.abcdefgh12.us-east-2", ".rds.amazonaws.com"]),
    _J(["mysql+pymysql://admin:", "hunter22pass@db:3306/x"]),
    _J(["bob.smith", "@", "realcorp.com"]),
])


def test_secrets_block_and_example_values_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "ROOT", tmp_path)
    ok = tmp_path / "ok.md"
    ok.write_text("mysql+pymysql://reports_ro:reports_ro@127.0.0.1:3307/jms  alice@example.com", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text(FAKE, encoding="utf-8")
    problems, warnings = bundle.scan([ok, bad])
    assert len(problems) == 4 and all(p.startswith("bad.md") for p in problems)
    assert len(warnings) == 1 and warnings[0].startswith("bad.md: 1 non-example email")


def test_local_state_and_secrets_are_never_included(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "ROOT", tmp_path)
    for rel in (".env", "rebo.yaml", "data/state.db", ".venv/x.py", ".vscode/s.json", "fixtures/demo/greenleaf.db", "src/a.py",
                ".env.example", "rebo.example.yaml", "fixtures/demo/rebo.yaml", "BUNDLE_MANIFEST.json",
                "rebo.git.bundle"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    kept = sorted(str(p.relative_to(tmp_path)).replace("\\", "/") for p in tmp_path.rglob("*") if p.is_file() and bundle.included(p))
    # a fixture's own rebo.yaml ships; the machine-local one at the top does not
    assert kept == [".env.example", "fixtures/demo/rebo.yaml", "rebo.example.yaml", "src/a.py"]


def test_the_real_folder_passes_the_scan():
    files = sorted(p for p in bundle.ROOT.rglob("*") if p.is_file() and bundle.included(p))
    problems, _ = bundle.scan(files)
    assert problems == []


def test_check_only_scans_without_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "ROOT", tmp_path)
    (tmp_path / "a.md").write_text("nothing secret", encoding="utf-8")
    out = tmp_path / "out.zip"
    monkeypatch.setattr("sys.argv", ["export_bundle.py", "--check-only", "--out", str(out)])
    assert bundle.main() == 0
    (tmp_path / "planted.env.txt").write_text(FAKE, encoding="utf-8")
    assert bundle.main() == 1
    assert not out.exists()
