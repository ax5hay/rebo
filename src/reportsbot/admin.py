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
from .settings import Settings, config_path, flatten_yaml, validate_yaml
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


def preview_config(app: "App", user: User, text: str) -> dict[str, Any]:
    """What saving `text` would do, without saving: validate it, parse every model string, build an App
    on it with a throw-away state dir, check the database answers `SELECT 1`, and list the settings
    that change (secrets masked). No model calls. Returns {ok, errors, changes, message}."""
    _owner_only(user)
    from .llm import parse
    from .service import App
    errors: list[str] = []
    try:
        validate_yaml(text)
    except ValueError as e:
        return {"ok": False, "errors": [f"configuration: {e}"], "changes": [],
                "message": msg.say("config_preview_bad", n=1)}
    flat = flatten_yaml(text)
    flat.setdefault("database_url", os.environ.get("REPORTSBOT_DATABASE_URL", ""))
    new = Settings.model_validate(flat)
    for key in ("model", "fast_model", "escalate_model"):
        if getattr(new, key):
            try:
                parse(getattr(new, key))
            except ValueError as e:
                errors.append(f"{key}: {e}")
    for spec in new.fallback_models:
        try:
            parse(spec)
        except ValueError as e:
            errors.append(f"fallback model: {e}")
    with tempfile.TemporaryDirectory(prefix="reportsbot-preview-") as tmp:
        try:
            trial = App(new.model_copy(update={"state_dir": Path(tmp)}))
            trial.target.run("SELECT 1", max_rows=1)
            trial.target.engine.dispose()
            trial.store.db.close()
        except Exception as e:
            errors.append(f"database: cannot connect ({str(getattr(e, 'orig', e)).splitlines()[0][:200]})")
    old, cur = app.settings.model_dump(), new.model_dump()
    secret = lambda k: any(w in k for w in ("key", "secret", "password"))  # noqa: E731
    changes = [{"setting": k, "from": "***" if secret(k) else str(old.get(k)), "to": "***" if secret(k) else str(v)}
               for k, v in cur.items() if k != "state_dir" and old.get(k) != v] + (
              [{"setting": "state_dir", "from": str(old["state_dir"]), "to": str(new.state_dir)}]
              if old.get("state_dir") != new.state_dir else [])
    message = msg.say("config_preview_ok", n=len(changes)) if not errors else msg.say("config_preview_bad",
                                                                                      n=len(errors))
    return {"ok": not errors, "errors": errors, "changes": changes, "message": message}


def save_config(app: "App", user: User, text: str, note: str = "", *, preview: bool = False) -> dict[str, Any]:
    """Validate and save atomically, with an audit record. preview=True: only report what would happen
    (preview_config); nothing is written."""
    if preview:
        return preview_config(app, user, text)
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


def import_knowledge(app: "App", user: User, text: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Apply an edited export. dry_run: change nothing; return the same counts plus `changes`, the list
    of what an import would do (add / edit with before -> after / share / withdraw), SQL checked."""
    if not user.is_admin:
        raise PermissionError("Only admins can import knowledge.")
    doc = yaml.safe_load(text) or {}
    counts: dict[str, Any] = {"added": 0, "updated": 0, "shared": 0, "retired": 0, "unchanged": 0, "errors": [],
                              "changes": [], "dry_run": dry_run}
    for n, entry in enumerate(doc.get("knowledge") or [], 1):
        try:
            if not entry.get("id"):
                if dry_run:
                    app._check_item_sql(entry["kind"], entry.get("sql"))
                    counts["changes"].append({"action": "add", "kind": entry["kind"], "title": entry["title"]})
                else:
                    app.add_knowledge(user, kind=entry["kind"], title=entry["title"], body=entry.get("body"),
                                      sql=entry.get("sql"), question=entry.get("question"))
                counts["added"] += 1
                continue
            item = app.knowledge.get(entry["id"])
            if not item:
                raise KeyError(f"unknown id {entry['id']}")
            changes = {k: entry.get(k) for k in app.knowledge.EDITABLE if k in entry and entry.get(k) != item.get(k)}
            if changes:
                if dry_run:
                    if "sql" in changes:
                        app._check_item_sql(item["kind"], changes["sql"])
                    counts["changes"].append({"action": "edit", "id": item["id"], "title": item["title"],
                                              "fields": {k: [item.get(k), v] for k, v in changes.items()}})
                else:
                    app.edit_knowledge(user, item["id"], changes)
                counts["updated"] += 1
            status = entry.get("status")
            if status == "verified" and item["status"] != "verified":
                scope = entry.get("scope") if entry.get("scope") in ("org", "team") else "org"
                if dry_run:
                    counts["changes"].append({"action": "share", "id": item["id"], "title": item["title"],
                                              "scope": scope})
                else:
                    app.promote(user, item["id"], scope)
                counts["shared"] += 1
            elif status == "retired" and item["status"] != "retired":
                if dry_run:
                    counts["changes"].append({"action": "withdraw", "id": item["id"], "title": item["title"]})
                else:
                    app.retire(user, item["id"], "withdrawn via import")
                counts["retired"] += 1
            elif not changes:
                counts["unchanged"] += 1
        except Exception as e:  # one bad entry must not block the rest; report it
            counts["errors"].append(f"entry {n} ({entry.get('title', '?')}): {e}")
    counts["message"] = msg.say("import_preview" if dry_run else "import_done",
                                **{k: counts[k] for k in ("added", "updated", "shared", "retired")},
                                errors=len(counts["errors"]))
    return counts


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")
