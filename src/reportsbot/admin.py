"""Administration that people do by hand (docs/22-roles-and-user-aids.md):

  owners  view / change / roll back reportsbot.yaml (validated, atomic, every version audited)
  admins  export everything the bot has learned to an editable YAML file, and import it back
          (each change goes through the same validation, history and undo as an edit in the UI)

Editing reportsbot.yaml directly on the server is equally supported: the file is the source of truth;
this module only adds validation, an audit trail and rollback for edits made through the API/UI.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from . import messages as msg
from .knowledge import User
from .settings import config_path, validate_yaml
from .store import now

if TYPE_CHECKING:
    from .service import App

_EXPORT_HEADER = """\
# Everything the bot has learned. Edit and import with:  reportsbot knowledge import <file>
#   - change title / question / body / sql of any item (kept in its history; Undo works)
#   - status: verified (share with everyone) or retired (withdraw); other statuses are set by the bot
#   - add a new item: leave out `id` (it is added as shared knowledge by the importing admin)
#   - removing an entry from this file does NOT delete it; set status: retired instead
"""
_FIELDS = ("id", "kind", "status", "scope", "owner", "team", "title", "question", "body", "sql")


def _owner_only(user: User) -> None:
    if not user.is_owner:
        raise PermissionError("Only owners can view or change the configuration.")


def get_config(app: "App", user: User) -> dict[str, Any]:
    _owner_only(user)
    path = config_path()
    return {"path": str(path.resolve()), "yaml": path.read_text(encoding="utf-8") if path.is_file() else "",
            "history": app.store.all("SELECT id, at, actor, note FROM config_event ORDER BY id DESC LIMIT 20")}


def save_config(app: "App", user: User, text: str, note: str = "") -> dict[str, Any]:
    _owner_only(user)
    validate_yaml(text)
    path = config_path()
    previous = path.read_text(encoding="utf-8") if path.is_file() else None
    fd, tmp = tempfile.mkstemp(dir=path.resolve().parent, prefix=".reportsbot.", suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)  # atomic: readers see the old or the new file, never half of one
    with app.store.tx() as db:
        db.execute("INSERT INTO config_event(at, actor, previous, current, note) VALUES(?,?,?,?,?)",
                   (now(), user.id, previous, text, note))
    return {"message": msg.say("config_saved")}


def rollback_config(app: "App", user: User, event_id: int) -> dict[str, Any]:
    _owner_only(user)
    ev = app.store.one("SELECT * FROM config_event WHERE id=?", (event_id,))
    if not ev or ev["previous"] is None:
        raise KeyError("No earlier version recorded for that change.")
    return save_config(app, user, ev["previous"], note=f"rollback of change {event_id}")


def export_knowledge(app: "App", user: User, include_retired: bool = False) -> str:
    if not user.is_admin:
        raise PermissionError("Only admins can export what the bot has learned.")
    where = "" if include_retired else "WHERE status != 'retired'"
    items = [{k: r[k] for k in _FIELDS if r.get(k) is not None}
             for r in app.store.all(f"SELECT * FROM knowledge {where} ORDER BY kind, title")]
    return _EXPORT_HEADER + yaml.safe_dump({"knowledge": items}, sort_keys=False, allow_unicode=True, width=110)


def import_knowledge(app: "App", user: User, text: str) -> dict[str, Any]:
    if not user.is_admin:
        raise PermissionError("Only admins can import knowledge.")
    doc = yaml.safe_load(text) or {}
    counts: dict[str, Any] = {"added": 0, "updated": 0, "shared": 0, "retired": 0, "unchanged": 0, "errors": []}
    for n, entry in enumerate(doc.get("knowledge") or [], 1):
        try:
            if not entry.get("id"):
                app.add_knowledge(user, kind=entry["kind"], title=entry["title"], body=entry.get("body"),
                                  sql=entry.get("sql"), question=entry.get("question"))
                counts["added"] += 1
                continue
            item = app.knowledge.get(entry["id"])
            if not item:
                raise KeyError(f"unknown id {entry['id']}")
            changes = {k: entry.get(k) for k in app.knowledge.EDITABLE if k in entry and entry.get(k) != item.get(k)}
            if changes:
                app.edit_knowledge(user, item["id"], changes)
                counts["updated"] += 1
            status = entry.get("status")
            if status == "verified" and item["status"] != "verified":
                app.promote(user, item["id"], entry.get("scope") if entry.get("scope") in ("org", "team") else "org")
                counts["shared"] += 1
            elif status == "retired" and item["status"] != "retired":
                app.retire(user, item["id"], "withdrawn via import")
                counts["retired"] += 1
            elif not changes:
                counts["unchanged"] += 1
        except Exception as e:  # one bad entry must not block the rest; report it
            counts["errors"].append(f"entry {n} ({entry.get('title', '?')}): {e}")
    counts["message"] = msg.say("import_done", **{k: counts[k] for k in ("added", "updated", "shared", "retired")},
                                errors=len(counts["errors"]))
    return counts


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
