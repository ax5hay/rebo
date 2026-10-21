import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_bundle", ROOT / "tools" / "export_bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def test_secrets_block_and_example_values_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "ROOT", tmp_path)
    ok = tmp_path / "ok.md"
    ok.write_text("mysql+pymysql://reports_ro:reports_ro@127.0.0.1:3307/jms  alice@example.com", encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text("key=sk-or-v1-" + "a" * 40 + "\nAKIA" + "B" * 16 + "\nprod-db.abcdefgh12.us-east-2.rds.amazonaws.com"
                   + "\nmysql+pymysql://admin:hunter22pass@db:3306/x\nbob.smith@realcorp.com", encoding="utf-8")
    problems, warnings = bundle.scan([ok, bad])
    assert len(problems) == 4 and all(p.startswith("bad.md") for p in problems)
    assert warnings == ["bad.md: 1 non-example email address(es), e.g. bob.smith@realcorp.com"]


def test_local_state_and_secrets_are_never_included(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "ROOT", tmp_path)
    for rel in (".env", "reportsbot.yaml", "data/state.db", ".venv/x.py", "fixtures/demo/greenleaf.db", "src/a.py",
                ".env.example", "reportsbot.example.yaml"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    kept = sorted(str(p.relative_to(tmp_path)).replace("\\", "/") for p in tmp_path.rglob("*") if p.is_file() and bundle.included(p))
    assert kept == [".env.example", "reportsbot.example.yaml", "src/a.py"]
