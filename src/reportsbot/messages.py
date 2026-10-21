"""Every sentence the bot shows a person, in one place (docs/05-ux-copy.md explains each).

Rules: plain business words, no SQL or table names unless the person opens "Show SQL";
always say *who* a change affects; never claim more certainty than the trust state.
"""
from __future__ import annotations

MESSAGES: dict[str, str] = {
    # --- answers -------------------------------------------------------------------
    "report_ready": "Here is {title}. {row_phrase}",
    "rows_all": "{n} row{s}.",
    "rows_truncated": "Showing the first {n} rows; there are more. Narrow the question or export the full result.",
    "rows_none": "No rows matched. The assumptions below explain what was searched for.",
    "assumptions_header": "How I read your question",
    "ask_feedback": "Is this right?",

    # --- provenance badges (shown above the table) --------------------------------------
    "prov_verified": "Verified report · checked by {who} on {when}",
    "prov_yours": "Same as a report you confirmed earlier",
    "prov_adapted": "Built from saved knowledge: {titles}",
    "prov_new": "New report · not checked by anyone yet",

    # --- feedback: "Yes, this is right" --------------------------------------------
    "confirm_saved_personal": (
        "Thanks, saved. Next time you ask something like this, I'll start from this report. "
        "This only tunes the bot for you; other people won't see the change unless an admin shares it."
    ),
    "confirm_reinforced": "Thanks. You've confirmed this report before, so I'll keep relying on it for you.",
    "confirm_matches_verified": "Thanks. This matches a report your team has already verified.",
    "confirm_auto_proposed": (
        "{n} people have now confirmed this same report, so I've sent it to an admin to share with everyone."
    ),

    # --- feedback: "No, fix it" -----------------------------------------------------------
    "fix_prompt": "What should be different? For example: \"only count active ones\" or \"use the date it was approved\".",
    "reject_retired_own": "Understood. I've stopped using the earlier report you confirmed for this.",
    "reject_flagged": (
        "Thanks for flagging this. The report was built from shared knowledge; I've noted your report "
        "for the admins. Your correction below applies to you right away."
    ),
    "reject_quarantined": (
        "Thanks. The shared knowledge behind this report is now on hold for everyone until an admin reviews it."
    ),

    # --- "Remember this?" cards ----------------------------------------------------------
    "remember_header": "Should I remember this for next time?",
    "remember_scope_note": "Only for you. An admin can share it with everyone later.",
    "teach_saved_personal": "Got it. I'll use \"{title}\" in your future questions. Only you are affected.",
    "teach_replaced_own": "Updated. Your earlier meaning of \"{title}\" is replaced (you can undo this in My knowledge).",
    "teach_conflicts_shared": (
        "Your team already has a shared meaning for \"{title}\": {shared_body}. I'll keep using the shared one "
        "for now and have sent your version to an admin to review."
    ),
    "remember_dismissed": "OK, I won't remember that.",

    # --- sharing ----------------------------------------------------------------------
    "share_requested": "Sent to an admin. Until it's approved it keeps working for you only.",
    "promoted": "Shared. Everyone in {scope} will now get answers that use \"{title}\".",
    "retired": "Withdrawn. It's no longer used. You can undo this from its history.",
    "restored": "Restored. \"{title}\" is back to {status}.",

    # --- direct editing ------------------------------------------------------------------
    "edited": "Saved. \"{title}\" now reads as you wrote it. The previous version is kept; use Undo to go back.",
    "edit_nothing": "Nothing changed.",
    "edit_undone": "Undone. \"{title}\" is back to its previous wording.",
    "added_shared": "Added for everyone: \"{title}\". It applies to the next question anyone asks.",
    "edit_bad_sql": "That SQL can't be saved: {error}",

    # --- clarifying -------------------------------------------------------------------
    "clarify_intro": "Quick check before I run this:",
    "clarify_other": "Something else (type it)",

    # --- trust labels (knowledge page) -----------------------------------------------------
    "status_active": "Yours: used only for you",
    "status_proposed": "Waiting for an admin: used only for you until approved",
    "status_verified": "Shared with {scope}",
    "status_stale": "Paused: the data it uses changed and it needs a re-check",
    "status_quarantined": "On hold: reported wrong, waiting for an admin",
    "status_retired": "Withdrawn",

    # --- system -------------------------------------------------------------------------
    "error_generic": "Something went wrong while building this report. Nothing was changed. Try rephrasing, or ask again.",
    "error_budget": "This question needed more work than one turn allows. Try splitting it into smaller questions.",
    "stale_notice": "{n} of your saved items need a re-check because the data they use changed.",
    "welcome": (
        "Ask for any report in plain words, for example \"active clients by stage this quarter\". "
        "When an answer is right, say so and I'll remember it for you. When it's wrong, tell me what to fix."
    ),
}


def say(key: str, **kw) -> str:
    return MESSAGES[key].format(**kw)


def rows_phrase(n: int, truncated: bool) -> str:
    if truncated:
        return say("rows_truncated", n=n)
    if n == 0:
        return say("rows_none")
    return say("rows_all", n=n, s="" if n == 1 else "s")


def status_label(status: str, scope: str = "org") -> str:
    return say(f"status_{status}", scope="your team" if scope == "team" else "the whole organisation")
