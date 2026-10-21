"""Learned knowledge and its trust lifecycle.

Four kinds of item, all learned from people in chat (never from config files):
  example  question -> SQL a person confirmed was right
  term     a business word -> its meaning (+ optional SQL predicate), e.g. "active client"
  note     any other fact or rule a person stated ("archived cases never count as open")
  join     how two tables connect when the schema does not say

Lifecycle (docs/04-learning-and-trust.md has the full state machine):
  active      personal: used for its owner only
  proposed    still personal, and waiting in the admin queue to be shared
  verified    shared: used for everyone in its scope (team or org)
  stale       the tables it uses changed and re-checking failed; not used until fixed
  quarantined reported wrong; not used until an admin decides
  retired     withdrawn or replaced; kept for audit and undo (valid_to is set)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .catalog import Catalog
from .retrieval import Index
from .safety import GuardError, canonical_hash, tables_in
from .store import Store, new_id, now

Role = Literal["user", "admin", "owner"]
USABLE = ("active", "proposed", "verified")
# Older names accepted from hosts and tokens.
ROLE_ALIASES = {"member": "user", "curator": "admin", "superadmin": "owner", "super_admin": "owner"}


def normalise_role(raw: str | None) -> Role:
    r = ROLE_ALIASES.get(str(raw or "").strip().lower(), str(raw or "").strip().lower())
    return r if r in ("user", "admin", "owner") else "user"  # type: ignore[return-value]


@dataclass(frozen=True)
class User:
    """user: asks, gives feedback, teaches for themselves, requests fixes.
    admin: also adds/edits/shares/withdraws any learned knowledge and handles requests.
    owner: also changes the configuration (docs/22-roles-and-user-aids.md)."""
    id: str
    role: Role = "user"
    team: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "role", normalise_role(self.role))

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "owner")

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


@dataclass
class Outcome:
    """What happened, for the UI to explain (keys map to copy.py)."""
    message: str
    item: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _row(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    for k in ("tables", "fingerprints", "result_signature", "confirmers"):
        if isinstance(item.get(k), str):
            item[k] = json.loads(item[k])
    return item


class Knowledge:
    def __init__(self, store: Store, index: Index, catalog: Catalog, dialect: str, share_threshold: int = 3):
        self.store, self.index, self.catalog = store, index, catalog
        self.dialect, self.share_threshold = dialect, share_threshold

    # ---- visibility --------------------------------------------------------------------
    def _visible_where(self, user: User) -> tuple[str, tuple]:
        return ("(status IN ('active','proposed','verified') AND owner=?) OR "
                "(status='verified' AND scope='org') OR "
                "(status='verified' AND scope='team' AND team IS NOT NULL AND team=?)", (user.id, user.team or ""))

    def visible(self, user: User, kind: str | None = None) -> list[dict[str, Any]]:
        where, args = self._visible_where(user)
        sql = f"SELECT * FROM knowledge WHERE ({where})" + (" AND kind=?" if kind else "")
        return [_row(r) for r in self.store.all(sql, args + ((kind,) if kind else ()))]

    def visible_ids(self, user: User) -> set[str]:
        where, args = self._visible_where(user)
        return {r["id"] for r in self.store.all(f"SELECT id FROM knowledge WHERE {where}", args)}

    def get(self, item_id: str) -> dict[str, Any] | None:
        return _row(self.store.one("SELECT * FROM knowledge WHERE id=?", (item_id,)))

    def mine(self, user: User) -> list[dict[str, Any]]:
        """Everything the user owns, any status, newest first (the 'What I've taught' page)."""
        return [_row(r) for r in self.store.all(
            "SELECT * FROM knowledge WHERE owner=? ORDER BY updated_at DESC", (user.id,))]

    def search(self, user: User, query: str, top: int = 6) -> list[dict[str, Any]]:
        ids = self.index.search_knowledge(query, self.visible_ids(user), top=top)
        items = [self.get(i) for i in ids]
        # Shared, verified knowledge first; then the user's own; most-confirmed first within each.
        rank = {"verified": 0, "proposed": 1, "active": 1}
        items = sorted([i for i in items if i], key=lambda i: (rank.get(i["status"], 2), -i["confirmations"]))
        # A shared term/note wins over the user's own differing version until an admin decides.
        seen: set[tuple[str, str]] = set()
        out = []
        for i in items:
            key = (i["kind"], i["title"].strip().lower())
            if i["kind"] in ("term", "note") and key in seen:
                continue
            seen.add(key)
            out.append(i)
        return out

    def learned_joins(self, user: User) -> list[dict[str, Any]]:
        out = []
        for item in self.visible(user, "join"):
            sql = item.get("sql") or ""
            left, _, right = sql.partition("=")
            if "." in left and "." in right:
                ft, fc = left.strip().split(".", 1)
                tt, tc = right.strip().split(".", 1)
                out.append({"from_table": ft, "from_cols": fc, "to_table": tt, "to_cols": tc,
                            "source": "learned", "confidence": 1.0, "item_id": item["id"]})
        return out

    # ---- writes ------------------------------------------------------------------------
    def _event(self, db, item_id: str, actor: str, action: str, frm: str | None, to: str | None, note: str = ""):
        db.execute("INSERT INTO knowledge_event(item_id, at, actor, action, from_status, to_status, note) "
                   "VALUES(?,?,?,?,?,?,?)", (item_id, now(), actor, action, frm, to, note))

    def _index_item(self, item: dict[str, Any]) -> None:
        with self.store.tx() as db:
            db.execute("DELETE FROM knowledge_fts WHERE id=?", (item["id"],))
            db.execute("INSERT INTO knowledge_fts(id, title, question, body) VALUES(?,?,?,?)",
                       (item["id"], item["title"], item.get("question") or "", item.get("body") or ""))
        text = " . ".join(x for x in (item["title"], item.get("question"), item.get("body")) if x)
        self.index.put_vectors([f"knowledge:{item['id']}"], [text])

    def _create(self, *, user: User, kind: str, title: str, status: str = "active", question: str | None = None,
                body: str | None = None, sql: str | None = None, source_turn: str | None = None,
                result_signature: dict | None = None, supersedes: str | None = None, note: str = "") -> dict:
        tables = tables_in(sql, self.dialect) if (sql and kind == "example") else []
        if kind == "join" and sql:
            tables = sorted({side.strip().split(".")[0] for side in sql.split("=") if "." in side})
        item_id = new_id(kind[:2])
        ts = now()
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO knowledge(id, kind, status, scope, owner, team, title, question, body, sql, sql_canonical,"
                " tables, fingerprints, result_signature, confirmations, confirmers, source_turn, supersedes,"
                " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, kind, status, "personal", user.id, user.team, title, question, body, sql,
                 canonical_hash(sql, self.dialect) if (sql and kind == "example") else None,
                 json.dumps(tables), json.dumps(self.catalog.fingerprints(tables)),
                 json.dumps(result_signature) if result_signature else None,
                 1 if kind == "example" else 0, json.dumps([user.id] if kind == "example" else []),
                 source_turn, supersedes, ts, ts))
            self._event(db, item_id, user.id, "created", None, status, note)
        item = self.get(item_id)
        self._index_item(item)
        return item

    def _similar_examples(self, question: str, exclude: set[str], top: int = 5) -> list[dict[str, Any]]:
        """Examples of *any* owner whose question resembles this one (keyword search only)."""
        from .retrieval import fts_query
        ids = [r["id"] for r in self.store.all(
            "SELECT id, bm25(knowledge_fts) AS s FROM knowledge_fts WHERE knowledge_fts MATCH ? ORDER BY s LIMIT 20",
            (fts_query(question),))]
        out = []
        for i in ids:
            item = self.get(i)
            if item and item["kind"] == "example" and item["status"] != "retired" and i not in exclude:
                out.append(item)
            if len(out) >= top:
                break
        return out

    def confirm_report(self, user: User, *, question: str, title: str, sql: str, turn_id: str,
                       result_signature: dict, equivalent: Callable[[str, str], bool] | None = None) -> Outcome:
        """A person said 'this report is right'. Reinforce a matching item or create a personal one.

        "Matching" = the same normalised SQL, or (when `equivalent` is given) a similar question's SQL
        that returns exactly the same rows. People phrase and write queries differently; agreement on
        the result is what counts."""
        canon = canonical_hash(sql, self.dialect)
        same = [_row(r) for r in self.store.all(
            "SELECT * FROM knowledge WHERE kind='example' AND sql_canonical=? AND status!='retired' "
            "ORDER BY created_at", (canon,))]
        if equivalent:
            for item in self._similar_examples(question, {i["id"] for i in same}):
                try:
                    if equivalent(sql, item["sql"]):
                        same.append(item)
                except Exception:
                    continue
            same.sort(key=lambda i: i["created_at"])
        visible = self.visible_ids(user)
        mine_or_shared = next((i for i in same if i["id"] in visible), None)
        if mine_or_shared:
            item = mine_or_shared
            confirmers = list(dict.fromkeys([*item["confirmers"], user.id]))
            with self.store.tx() as db:
                db.execute("UPDATE knowledge SET confirmations=confirmations+1, confirmers=?, updated_at=? WHERE id=?",
                           (json.dumps(confirmers), now(), item["id"]))
                self._event(db, item["id"], user.id, "confirmed", item["status"], item["status"])
            outcome = Outcome("confirm_matches_verified" if item["status"] == "verified" else "confirm_reinforced",
                              self.get(item["id"]))
        else:
            item = self._create(user=user, kind="example", title=title, question=question, sql=sql,
                                source_turn=turn_id, result_signature=result_signature)
            outcome = Outcome("confirm_saved_personal", item)
        # Independent agreement: N different people confirmed the same query -> queue it for sharing.
        people = {p for i in [*same, outcome.item] if i for p in (i.get("confirmers") or [])}
        if len(people) >= self.share_threshold and not any(i["status"] in ("proposed", "verified") for i in same):
            target = same[0] if same else outcome.item
            self._set_status(target["id"], "proposed", actor="system",
                             note=f"{len(people)} people confirmed this same query independently")
            outcome.extra["auto_proposed"] = len(people)
        return outcome

    def reject(self, user: User, item_ids: list[str], reason: str) -> list[Outcome]:
        """A person said a report built from these items was wrong."""
        out = []
        for item_id in item_ids:
            item = self.get(item_id)
            if not item or item["status"] not in USABLE:
                continue
            with self.store.tx() as db:
                db.execute("UPDATE knowledge SET rejections=rejections+1, updated_at=? WHERE id=?", (now(), item_id))
                self._event(db, item_id, user.id, "reported_wrong", item["status"], item["status"], reason)
            if item["owner"] == user.id and item["status"] != "verified":
                self._set_status(item_id, "retired", actor=user.id, note="owner reported it wrong")
                out.append(Outcome("reject_retired_own", self.get(item_id)))
            elif user.is_admin or item["rejections"] + 1 >= 2:
                self._set_status(item_id, "quarantined", actor=user.id, note=reason)
                out.append(Outcome("reject_quarantined", self.get(item_id)))
            else:
                out.append(Outcome("reject_flagged", self.get(item_id)))
        return out

    def teach(self, user: User, *, kind: str, title: str, body: str, sql: str | None,
              source_turn: str | None) -> Outcome:
        """Save a fact the user agreed to have remembered (from a 'Remember this?' card)."""
        same_title = [i for i in self.visible(user, kind) if i["title"].strip().lower() == title.strip().lower()]
        shared = next((i for i in same_title if i["owner"] != user.id and i["status"] == "verified"), None)
        own = next((i for i in same_title if i["owner"] == user.id), None)
        if shared:
            item = self._create(user=user, kind=kind, title=title, body=body, sql=sql, source_turn=source_turn,
                                status="proposed", note=f"differs from shared item {shared['id']}")
            return Outcome("teach_conflicts_shared", item, {"shared": shared})
        item = self._create(user=user, kind=kind, title=title, body=body, sql=sql, source_turn=source_turn,
                            supersedes=own["id"] if own else None)
        if own:
            self._set_status(own["id"], "retired", actor=user.id, note=f"replaced by {item['id']}")
            return Outcome("teach_replaced_own", item, {"previous": own})
        return Outcome("teach_saved_personal", item)

    def _set_status(self, item_id: str, status: str, *, actor: str, note: str = "", scope: str | None = None) -> dict:
        item = self.get(item_id)
        ts = now()
        with self.store.tx() as db:
            db.execute("UPDATE knowledge SET status=?, scope=COALESCE(?, scope), updated_at=?, "
                       "valid_to=CASE WHEN ?='retired' THEN ? ELSE NULL END WHERE id=?",
                       (status, scope, ts, status, ts, item_id))
            self._event(db, item_id, actor, f"status:{status}", item["status"], status, note)
        return self.get(item_id)

    def share(self, user: User, item_id: str) -> Outcome:
        item = self.get(item_id)
        if not item or item["owner"] != user.id:
            raise PermissionError("Only the owner can ask to share an item.")
        if user.is_admin:
            return Outcome("promoted", self._promote(user, item, "org"))
        return Outcome("share_requested", self._set_status(item_id, "proposed", actor=user.id, note="owner asked to share"))

    def _promote(self, admin: User, item: dict, scope: str) -> dict:
        with self.store.tx() as db:
            db.execute("UPDATE knowledge SET verified_by=?, verified_at=? WHERE id=?", (admin.id, now(), item["id"]))
        return self._set_status(item["id"], "verified", actor=admin.id, scope=scope, note=f"shared with {scope}")

    def promote(self, admin: User, item_id: str, scope: str = "org") -> Outcome:
        if not admin.is_admin:
            raise PermissionError("Only admins can share knowledge with others.")
        item = self.get(item_id)
        if not item:
            raise KeyError(item_id)
        if scope == "team" and not item.get("team"):
            scope = "org"
        return Outcome("promoted", self._promote(admin, item, scope))

    def retire(self, user: User, item_id: str, reason: str = "") -> Outcome:
        item = self.get(item_id)
        if not item or (item["owner"] != user.id and not user.is_admin):
            raise PermissionError("Only the owner or an admin can withdraw this.")
        return Outcome("retired", self._set_status(item_id, "retired", actor=user.id, note=reason))

    def restore(self, user: User, item_id: str) -> Outcome:
        """Undo the last status change (owner for personal items, admin for anything)."""
        item = self.get(item_id)
        if not item or (item["owner"] != user.id and not user.is_admin):
            raise PermissionError("Only the owner or an admin can undo this.")
        last = self.store.one("SELECT from_status FROM knowledge_event WHERE item_id=? AND action LIKE 'status:%' "
                              "ORDER BY id DESC LIMIT 1", (item_id,))
        back = (last or {}).get("from_status") or "active"
        if back == "verified" and not user.is_admin:
            back = "proposed"
        return Outcome("restored", self._set_status(item_id, back, actor=user.id, note="undo"))

    def mark_used(self, item_ids: list[str]) -> None:
        if item_ids:
            with self.store.tx() as db:
                db.executemany("UPDATE knowledge SET uses=uses+1, last_used_at=? WHERE id=?",
                               [(now(), i) for i in item_ids])

    def review_queue(self) -> list[dict[str, Any]]:
        return [_row(r) for r in self.store.all(
            "SELECT * FROM knowledge WHERE status IN ('proposed','quarantined') ORDER BY updated_at")]

    def history(self, item_id: str) -> list[dict[str, Any]]:
        return self.store.all("SELECT * FROM knowledge_event WHERE item_id=? ORDER BY id", (item_id,))

    # ---- schema drift -----------------------------------------------------------------
    def revalidate(self, check_sql) -> dict[str, int]:
        """Re-check every SQL-bearing item whose tables changed since it was confirmed.
        `check_sql(sql)` raises on failure (guard + a 1-row execution)."""
        counts = {"checked": 0, "unchanged": 0, "repaired": 0, "stale": 0}
        for item in [_row(r) for r in self.store.all(
                "SELECT * FROM knowledge WHERE sql IS NOT NULL AND status IN ('active','proposed','verified','stale')")]:
            current = self.catalog.fingerprints(item["tables"] or [])
            changed = current != (item["fingerprints"] or {}) or len(current) != len(item["tables"] or [])
            if not changed and item["status"] != "stale":
                counts["unchanged"] += 1
                continue
            counts["checked"] += 1
            try:
                if item["kind"] == "example":
                    check_sql(item["sql"])
                elif len(current) != len(item["tables"] or []):
                    raise GuardError("a table it uses no longer exists")
                with self.store.tx() as db:
                    db.execute("UPDATE knowledge SET fingerprints=?, updated_at=? WHERE id=?",
                               (json.dumps(current), now(), item["id"]))
                if item["status"] == "stale":
                    last = self.store.one("SELECT from_status FROM knowledge_event WHERE item_id=? AND "
                                          "to_status='stale' ORDER BY id DESC LIMIT 1", (item["id"],))
                    self._set_status(item["id"], (last or {}).get("from_status") or "active", actor="system",
                                     note="re-checked after schema change: still works")
                    counts["repaired"] += 1
            except Exception as e:
                if item["status"] != "stale":
                    self._set_status(item["id"], "stale", actor="system", note=f"schema changed: {str(e)[:200]}")
                counts["stale"] += 1
        return counts
