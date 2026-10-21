"""HTTP API. A host application (e.g. JMS) calls this from behind its own login and passes
who the user is in headers. See docs/09-api-and-ui.md for every route and payload.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .knowledge import ROLE_ALIASES, User, normalise_role  # noqa: F401
from . import admin
from .service import App


class AskIn(BaseModel):
    text: str
    conversation_id: str | None = None


class FeedbackIn(BaseModel):
    verdict: Literal["correct", "wrong"]
    note: str = ""


class DefaultIn(BaseModel):
    value: str


class DrillIn(BaseModel):
    row: int
    column: str | None = None


class RememberIn(BaseModel):
    accept: bool


class PromoteIn(BaseModel):
    scope: Literal["org", "team"] = "org"


class ReasonIn(BaseModel):
    reason: str = ""


class KnowledgeIn(BaseModel):
    kind: Literal["example", "term", "note", "join"]
    title: str
    body: str | None = None
    sql: str | None = None
    question: str | None = None
    scope: Literal["org", "team"] = "org"


class RequestIn(BaseModel):
    kind: Literal["fix_knowledge", "fix_report", "access", "config", "other"]
    text: str
    item_id: str | None = None
    turn_id: str | None = None


class ResolveIn(BaseModel):
    status: Literal["done", "declined"]
    resolution: str = ""


class ConfigIn(BaseModel):
    yaml: str
    note: str = ""


class ImportIn(BaseModel):
    yaml: str
    dry_run: bool = False


class KnowledgeEdit(BaseModel):
    title: str | None = None
    question: str | None = None
    body: str | None = None
    sql: str | None = None


def user_from_headers(x_user_id: str = Header(...), x_user_role: str = Header("user"),
                      x_user_team: str | None = Header(None)) -> User:
    """auth.mode=headers: identity comes from the host app's gateway. Never expose without one."""
    if x_user_role.strip().lower() not in {"user", "admin", "owner", *ROLE_ALIASES}:
        raise HTTPException(400, "X-User-Role must be user, admin or owner")
    return User(id=x_user_id, role=x_user_role, team=x_user_team)  # type: ignore[arg-type]


def decode_jwt(token: str, settings) -> dict:
    """HS256 bearer token signed by the host with REPORTSBOT_JWT_SECRET and issued by auth.issuer."""
    import jwt

    if not settings.jwt_secret:
        raise HTTPException(500, "REPORTSBOT_JWT_SECRET is not set")
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid token: {e}") from e
    if claims.get("iss") != settings.jwt_issuer:
        raise HTTPException(401, "Invalid token issuer")
    return claims


def user_from_claims(claims: dict) -> User:
    """Claim names: user id = sub | user_id; role = role (user|admin|owner); team = team | tenant_id."""
    uid = claims.get("sub") or claims.get("user_id")
    if uid in (None, ""):
        raise HTTPException(401, "Token has no user id (sub or user_id)")
    role = normalise_role(claims.get("role"))
    team = claims.get("team") or claims.get("tenant_id")
    return User(id=str(uid), role=role, team=str(team) if team is not None else None)


def auth_dependency(app: App):
    if app.settings.auth_mode == "jwt":
        def user_from_jwt(authorization: str = Header(...)) -> User:
            if not authorization.startswith("Bearer "):
                raise HTTPException(401, "Missing Bearer token")
            return user_from_claims(decode_jwt(authorization.removeprefix("Bearer ").strip(), app.settings))
        return user_from_jwt
    return user_from_headers


def router(app: App) -> APIRouter:
    r = APIRouter(prefix="/api")
    current_user = auth_dependency(app)

    def guard_errors(fn):
        try:
            return fn()
        except PermissionError as e:
            raise HTTPException(403, str(e)) from e
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @r.get("/health")
    def health():
        return {"ok": True, "bootstrapped_at": app.store.meta_get("bootstrapped_at")}

    @r.post("/ask")
    async def ask(body: AskIn, user: User = Depends(current_user)):
        return await app.ask(user, body.text, body.conversation_id)

    @r.post("/turns/{turn_id}/feedback")
    def feedback(turn_id: str, body: FeedbackIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.feedback(user, turn_id, body.verdict, body.note))

    @r.post("/turns/{turn_id}/drill")
    def drill(turn_id: str, body: DrillIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.drill(user, turn_id, body.row, body.column))

    @r.post("/turns/{turn_id}/pin")
    def pin(turn_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.pin(user, turn_id))

    @r.delete("/knowledge/{item_id}/pin")
    def unpin(item_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.unpin(user, item_id))

    @r.post("/turns/{turn_id}/rerun")
    def rerun(turn_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.rerun(user, turn_id))

    @r.get("/turns/{turn_id}/csv", response_class=PlainTextResponse)
    def turn_csv(turn_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.turn_csv(user, turn_id))

    @r.get("/starter")
    def starter(user: User = Depends(current_user)):
        return app.starter_questions(user)

    @r.delete("/turns/{turn_id}/feedback")
    def undo_feedback(turn_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.undo_feedback(user, turn_id))

    @r.post("/requests")
    def create_request(body: RequestIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.create_request(user, **body.model_dump()))

    @r.get("/requests")
    def list_requests(status: str | None = "open", user: User = Depends(current_user)):
        return app.list_requests(user, status or None)

    @r.post("/requests/{request_id}/resolve")
    def resolve_request(request_id: str, body: ResolveIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.resolve_request(user, request_id, body.status, body.resolution))

    @r.post("/suggestions/{suggestion_id}")
    def remember(suggestion_id: str, body: RememberIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.remember(user, suggestion_id, body.accept))

    @r.get("/knowledge")
    def knowledge(user: User = Depends(current_user)):
        return app.my_knowledge(user)

    @r.post("/knowledge")
    def add_knowledge(body: KnowledgeIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.add_knowledge(user, **body.model_dump()))

    @r.patch("/knowledge/{item_id}")
    def edit_knowledge(item_id: str, body: KnowledgeEdit, user: User = Depends(current_user)):
        return guard_errors(lambda: app.edit_knowledge(user, item_id, body.model_dump(exclude_none=True)))

    @r.get("/knowledge/{item_id}/history")
    def history(item_id: str, user: User = Depends(current_user)):
        return app.knowledge.history(item_id)

    @r.post("/knowledge/{item_id}/share")
    def share(item_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.share(user, item_id))

    @r.post("/knowledge/{item_id}/promote")
    def promote(item_id: str, body: PromoteIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.promote(user, item_id, body.scope))

    @r.post("/knowledge/{item_id}/retire")
    def retire(item_id: str, body: ReasonIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.retire(user, item_id, body.reason))

    @r.post("/knowledge/{item_id}/restore")
    def restore(item_id: str, user: User = Depends(current_user)):
        return guard_errors(lambda: app.restore(user, item_id))

    @r.get("/review")
    def review(user: User = Depends(current_user)):
        return guard_errors(lambda: app.review_queue(user))

    @r.get("/admin/preview")
    def preview(user_id: str = Query(..., alias="user"), q: str = "", team: str | None = None,
                user: User = Depends(current_user)):
        return guard_errors(lambda: app.preview_as(user, user_id, q, team))

    @r.get("/admin/config")
    def get_config(user: User = Depends(current_user)):
        return guard_errors(lambda: admin.get_config(app, user))

    @r.put("/admin/config")
    def save_config(body: ConfigIn, user: User = Depends(current_user)):
        return guard_errors(lambda: admin.save_config(app, user, body.yaml, body.note))

    @r.post("/admin/config/rollback/{event_id}")
    def rollback_config(event_id: int, user: User = Depends(current_user)):
        return guard_errors(lambda: admin.rollback_config(app, user, event_id))

    @r.get("/defaults")
    def defaults(user: User = Depends(current_user)):
        return app.my_defaults(user)

    @r.put("/defaults/{name}")
    def set_default(name: str, body: DefaultIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.set_default(user, name, body.value))

    @r.get("/knowledge/about")
    def about(q: str, user: User = Depends(current_user)):
        return app.about(user, q)

    @r.get("/knowledge/export", response_class=PlainTextResponse)
    def export_knowledge(include_retired: bool = False, user: User = Depends(current_user)):
        return guard_errors(lambda: admin.export_knowledge(app, user, include_retired))

    @r.post("/knowledge/import")
    def import_knowledge(body: ImportIn, user: User = Depends(current_user)):
        return guard_errors(lambda: admin.import_knowledge(app, user, body.yaml, dry_run=body.dry_run))

    @r.post("/admin/revalidate")
    def revalidate(user: User = Depends(current_user)):
        if not user.is_admin:
            raise HTTPException(403, "admins only")
        return app.revalidate()

    return r


def create_app(app: App, *, with_ui: bool = True) -> FastAPI:
    api = FastAPI(title="reportsbot")
    api.include_router(router(app))
    for name in app.settings.adapters:  # optional host contracts (src/reportsbot/adapters/<name>.py)
        import importlib
        api.include_router(importlib.import_module(f".adapters.{name}", __package__).router(app))
    if with_ui:
        from .ui import mount_ui
        mount_ui(api, app)
    return api
