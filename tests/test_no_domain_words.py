"""Guard (AGENTS.md §1): no table name from a test database appears in src/ outside adapters/.

Domain meaning comes from the database and from people, never from code. Table names that are
also plain English words ("user", "status", "event") are allowed; anything else, such as a
compound identifier like a JMS table, fails the test.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "reportsbot"
# Table names that are ordinary words in this code base's own vocabulary.
PLAIN_WORDS = {"admin", "building", "contact", "contract", "err", "event", "form", "maintenance", "provider",
               "retrieval", "status", "template", "unit", "user"}


def domain_table_names() -> set[str]:
    names: set[str] = set()
    for p in ROOT.glob("fixtures/*/profile.json"):
        names |= set(json.loads(p.read_text(encoding="utf-8"))["tables"])
    build = (ROOT / "fixtures" / "demo_property" / "build.py").read_text(encoding="utf-8")
    names |= set(re.findall(r"CREATE TABLE (\w+)", build))
    return names - PLAIN_WORDS


def hits(text: str, names: set[str]) -> list[str]:
    return sorted(n for n in names if re.search(rf"\b{re.escape(n)}\b", text))


def test_fixture_tables_are_found():
    names = domain_table_names()
    assert "gc_case" in names and "lease" in names


def test_no_domain_table_names_in_src():
    names = domain_table_names()
    found = {}
    for f in SRC.rglob("*.py"):
        if "adapters" in f.relative_to(SRC).parts:
            continue
        if h := hits(f.read_text(encoding="utf-8"), names):
            found[str(f.relative_to(ROOT))] = h
    assert found == {}, f"domain table names in src/ (move them to an adapter or to learned knowledge): {found}"


def test_a_planted_name_is_caught():
    agent = (SRC / "agent.py").read_text(encoding="utf-8")
    assert hits(agent + "\nSELECT * FROM gc_case\n", domain_table_names()) == ["gc_case"]
