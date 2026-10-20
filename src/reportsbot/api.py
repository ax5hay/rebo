"""HTTP API. A host application (e.g. JMS) calls this from behind its own login and passes
who the user is in headers. See docs/09-api-and-ui.md for every route and payload.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .knowledge import User
from .service import App


class AskIn(BaseModel):
    text: str
    conversation_id: str | None = None


class FeedbackIn(BaseModel):
    verdict: Literal["correct", "wrong"]
    note: str = ""


class RememberIn(BaseModel):
    accept: bool


class PromoteIn(BaseModel):
    scope: Literal["org", "team"] = "org"


class ReasonIn(BaseModel):
    reason: str = ""


def current_user(x_user_id: str = Header(...), x_user_role: str = Header("member"),
                 x_user_team: str | None = Header(None)) -> User:
    """Identity comes from the host app's gateway. Never expose this API without one."""
    if x_user_role not in ("member", "curator"):
        raise HTTPException(400, "X-User-Role must be member or curator")
    return User(id=x_user_id, role=x_user_role, team=x_user_team)  # type: ignore[arg-type]


def router(app: App) -> APIRouter:
    r = APIRouter(prefix="/api")

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

    @r.post("/suggestions/{suggestion_id}")
    def remember(suggestion_id: str, body: RememberIn, user: User = Depends(current_user)):
        return guard_errors(lambda: app.remember(user, suggestion_id, body.accept))

    @r.get("/knowledge")
    def knowledge(user: User = Depends(current_user)):
        return app.my_knowledge(user)

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

    @r.post("/admin/revalidate")
    def revalidate(user: User = Depends(current_user)):
        if not user.is_curator:
            raise HTTPException(403, "curators only")
        return app.revalidate()

    return r


def create_app(app: App, *, with_ui: bool = True) -> FastAPI:
    api = FastAPI(title="reportsbot")
    api.include_router(router(app))
    if with_ui:
        from .ui import mount_ui
        mount_ui(api, app)
    return api
