"""Row-level security passthrough (B-058): each person's queries run as their own database role, so
the database's policies decide the rows. PostgreSQL only; runs when REBO_TEST_STATE_URL is set."""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from rebo.target import TargetDB

PG_URL = os.environ.get("REBO_TEST_STATE_URL", "")


def test_a_role_on_a_database_without_roles_is_refused(tmp_path):
    t = TargetDB(f"sqlite:///{tmp_path / 'x.db'}")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        with t.acting_as("alice"):
            pass
    with t.acting_as(None):  # off: nothing changes
        assert t.run("SELECT 1", max_rows=1).rows == [[1]]


@pytest.mark.skipif(not PG_URL, reason="needs PostgreSQL (REBO_TEST_STATE_URL)")
def test_each_person_sees_only_the_rows_their_role_may_see():
    url = PG_URL.replace("postgresql://", "postgresql+psycopg://", 1) if PG_URL.startswith("postgresql://") else PG_URL
    tag = uuid.uuid4().hex[:8]
    schema, alice, bob = f"rls_{tag}", f"alice_{tag}", f"bob_{tag}"
    admin = create_engine(url)
    with admin.begin() as c:
        c.execute(text(f"CREATE SCHEMA {schema}"))
        c.execute(text(f"CREATE TABLE {schema}.deal (owner text, amount int)"))
        c.execute(text(f"INSERT INTO {schema}.deal VALUES ('{alice}', 10), ('{alice}', 5), ('{bob}', 7)"))
        c.execute(text(f"ALTER TABLE {schema}.deal ENABLE ROW LEVEL SECURITY"))
        c.execute(text(f"CREATE POLICY mine ON {schema}.deal USING (owner = current_user)"))
        for r in (alice, bob):
            c.execute(text(f"CREATE ROLE {r} NOLOGIN"))
            c.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {r}"))
            c.execute(text(f"GRANT SELECT ON {schema}.deal TO {r}"))
    t = TargetDB(url)
    sql = f"SELECT SUM(amount) FROM {schema}.deal"
    try:
        with t.acting_as(alice):
            assert t.run(sql, max_rows=5).rows == [[15]]
        with t.acting_as(bob):
            assert t.run(sql, max_rows=5).rows == [[7]]
        assert t.run(sql, max_rows=5).rows == [[22]]          # the login itself (owner) after the roles
        with t.acting_as(f"nobody_{tag}"), pytest.raises(Exception, match="does not exist"):
            t.run(sql, max_rows=5)                              # unknown person: refused, never the login's rows
    finally:
        t.engine.dispose()
        with admin.begin() as c:
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            for r in (alice, bob):
                c.execute(text(f"DROP ROLE {r}"))
        admin.dispose()


def test_the_role_comes_from_the_person_and_the_configured_pattern(app, monkeypatch):
    from contextlib import nullcontext

    from rebo.knowledge import User
    seen = []
    monkeypatch.setattr(app.target, "acting_as", lambda role: seen.append(role) or nullcontext())
    app.as_user(User("ada"))
    app.settings.database_role = "rebo_{user}"
    app.as_user(User("ada"))
    assert seen == [None, "rebo_ada"]
