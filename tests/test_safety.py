import pytest

from rebo.safety import GuardError, canonical_hash, guard

SCHEMA = {"a": {"id": "int", "name": "varchar", "secret": "varchar"}, "b": {"a_id": "int", "v": "int"}}
SENSITIVE = {("a", "secret")}


def g(sql, cap=501):
    return guard(sql, dialect="mysql", schema=SCHEMA, sensitive=SENSITIVE, row_cap=cap)


@pytest.mark.parametrize("sql", [
    "delete from a", "update a set name='x'", "insert into a values (1,'x','y')", "drop table a",
    "select id from a; select 1", "select sleep(5)", "select id from a for update", "select id into @v from a",
    "show tables", "set @x = 1", "select benchmark(1000000, md5('x'))",
])
def test_rejects_non_read_only(sql):
    with pytest.raises(GuardError):
        g(sql)


def test_unknown_table_and_column_rejected_with_hint():
    with pytest.raises(GuardError, match="search_schema"):
        g("select * from nope")
    with pytest.raises(GuardError, match="describe_table"):
        g("select nope from a")


def test_protected_column_blocked_even_through_star():
    with pytest.raises(GuardError, match="protected"):
        g("select * from a")
    with pytest.raises(GuardError, match="protected"):
        g("select secret from a")


def test_limit_applied_and_smaller_limit_kept():
    assert "LIMIT 501" in g("select id from a").sql
    assert "LIMIT 5" in g("select id from a limit 5").sql
    assert "LIMIT 501" in g("select id from a limit 100000").sql


def test_cte_and_union_allowed_and_tables_reported():
    r = g("with x as (select id from a) select id from x union select a_id from b")
    assert r.tables == {"a", "b"}


def test_percent_and_colon_literals_survive():
    r = g("select name from a where name like '%x%' and name <> '10:30'")
    assert "'%x%'" in r.sql and "'10:30'" in r.sql


def test_canonical_hash_ignores_format_and_limit():
    assert canonical_hash("SELECT id FROM a LIMIT 5", "mysql") == canonical_hash("select  id\nfrom a", "mysql")
    assert canonical_hash("select id from a", "mysql") != canonical_hash("select name from a", "mysql")
