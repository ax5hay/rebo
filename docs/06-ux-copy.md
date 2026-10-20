# 06 · What the user sees and reads

Every sentence lives in `src/reportsbot/messages.py` (`MESSAGES`, `say()`). Front ends must use these
keys rather than writing their own text, so behaviour and wording change together.

## 1. Writing rules

1. **Plain business words.** No table names, column names or SQL in messages or assumptions.
   SQL appears only under **Show SQL**.
2. **Always say who a change affects.** Every learning message ends by saying whether it affects
   *only you*, *your team* or *everyone*.
3. **Never overstate certainty.** The badge says exactly what checked the answer: a curator, the
   user, saved knowledge, or nobody.
4. **One question at a time.** A clarification offers 2–4 concrete options plus a typed "something else".
5. **Every action is reversible and the user is told so** ("you can undo this in My knowledge").

## 2. The report card

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Verified report · checked by cora on 2026-10-21]          ← provenance badge │
│ Here is Active surrogates in screening. 47 rows.            ← report_ready    │
│ ┌──────────────┬───────────────┬──────────────┬───────────┐                  │
│ │ Surrogate    │ Stage         │ Sub-stage    │ Status    │  ← table, 15/page │
│ └──────────────┴───────────────┴──────────────┴───────────┘                  │
│ ▾ How I read your question                                  ← assumptions     │
│   • "Surrogates" means journeys of type surrogate, not people's contact type  │
│   • "In Screening" means the journey's current stage is Screening             │
│   • Only active journeys (archived and closed ones are excluded)              │
│ ▸ Show SQL                                                                    │
│ Is this right?  [ Yes, this is right ]  [ No, fix it ]                        │
└──────────────────────────────────────────────────────────────────────────────┘
┌ Should I remember this for next time? ───────────────────────────────────────┐  ← only if learnable
│ active surrogate: a surrogate journey that is not archived or closed          │
│ Only for you. A curator can share it with everyone later.                      │
│ [ Remember ]  [ No thanks ]                                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Element | Key / source | Rule |
|---|---|---|
| Badge | `prov_verified`, `prov_yours`, `prov_adapted`, `prov_new` | Colour: verified=green, yours=blue, adapted=light blue, new=grey (`ui._BADGE`) |
| Headline | `report_ready` + `rows_all` / `rows_truncated` / `rows_none` | Truncated wording appears when more than `REPORTSBOT_ROW_LIMIT` rows exist |
| Assumptions | `Report.assumptions` (from the model) | Always expanded. The prompt forbids table/column names here |
| Show SQL | `Report.sql` | Collapsed. The executed SQL may also carry the row cap |
| Feedback row | `ask_feedback` | Replaced by the outcome sentence after a click |

## 3. Feedback sentences, verbatim

| When | Key | Text |
|---|---|---|
| First **Yes** on a new report | `confirm_saved_personal` | Thanks, saved. Next time you ask something like this, I'll start from this report. This only tunes the bot for you; other people won't see the change unless a curator shares it. |
| **Yes** on a report the user had confirmed before | `confirm_reinforced` | Thanks. You've confirmed this report before, so I'll keep relying on it for you. |
| **Yes** on a report that matches shared knowledge | `confirm_matches_verified` | Thanks. This matches a report your team has already verified. |
| …and it was the 3rd distinct confirmer | `confirm_auto_proposed` (appended) | {n} people have now confirmed this same report, so I've sent it to a curator to share with everyone. |
| **No, fix it**, always ends with | `fix_prompt` | What should be different? For example: "only count active ones" or "use the date it was approved". |
| …the user's own saved report was behind it | `reject_retired_own` | Understood. I've stopped using the earlier report you confirmed for this. |
| …shared knowledge was behind it (1st report) | `reject_flagged` | Thanks for flagging this. The report was built from shared knowledge; I've noted your report for the curators. Your correction below applies to you right away. |
| …shared knowledge put on hold | `reject_quarantined` | Thanks. The shared knowledge behind this report is now on hold for everyone until a curator reviews it. |

## 4. Remember-this cards

| When | Key | Text |
|---|---|---|
| Card title | `remember_header` | Should I remember this for next time? |
| Card footnote | `remember_scope_note` | Only for you. A curator can share it with everyone later. |
| Remember (new) | `teach_saved_personal` | Got it. I'll use "{title}" in your future questions. Only you are affected. |
| Remember (replaces own) | `teach_replaced_own` | Updated. Your earlier meaning of "{title}" is replaced (you can undo this in My knowledge). |
| Remember (conflicts with shared) | `teach_conflicts_shared` | Your team already has a shared meaning for "{title}": {shared_body}. I'll keep using the shared one for now and have sent your version to a curator to review. |
| No thanks | `remember_dismissed` | OK, I won't remember that. |

## 5. Sharing and the knowledge page

| When | Key | Text |
|---|---|---|
| Member presses **Share with everyone** | `share_requested` | Sent to a curator. Until it's approved it keeps working for you only. |
| Curator approves | `promoted` | Shared. Everyone in {scope} will now get answers that use "{title}". |
| Withdraw | `retired` | Withdrawn. It's no longer used. You can undo this from its history. |
| Undo | `restored` | Restored. "{title}" is back to {status}. |
| Stale items exist | `stale_notice` | {n} of your saved items need a re-check because the data they use changed. |

Status labels (`status_label()`): see doc 05 §2.

## 6. Clarification card

```
Quick check before I run this:                                   ← clarify_intro
Do you mean cases assigned to Andrew Lee (admin) or Andrew Park (coordinator)?
Both exist, and they own different cases.                         ← why
[ Andrew Lee ]  [ Andrew Park ]                                   ← options; clicking sends the text
```

When to ask is policy in the prompt (doc 04 §5): only when the evidence disagrees.

## 7. Errors

| Key | Text | When |
|---|---|---|
| `error_generic` | Something went wrong while building this report. Nothing was changed. Try rephrasing, or ask again. | Model/API failure (logged with stack trace) |
| `error_budget` | This question needed more work than one turn allows. Try splitting it into smaller questions. | `UsageLimitExceeded` (40 requests or 25 tool calls) |

## 8. A full conversation (expected behaviour)

```
alice  ▸ Show me active surrogates in Screening and their current substage.
bot    ▸ [New report · not checked by anyone yet] Here is Active surrogates in Screening. 47 rows.
         How I read your question: surrogate = journey type surrogate; Screening = current stage;
         active = not archived or closed.
alice  ▸ [Yes, this is right]
bot    ▸ Thanks, saved. Next time you ask something like this, I'll start from this report.
         This only tunes the bot for you; other people won't see the change unless a curator shares it.

bob    ▸ active surrogates in screening please
bot    ▸ [New report · not checked by anyone yet] …        ← Alice's item is invisible to Bob
bob    ▸ [No, fix it]
bot    ▸ What should be different? …
bob    ▸ only the ones with a signed agreement
bot    ▸ [New report …] … 12 rows.
         ┌ Should I remember this for next time? ┐
         │ active surrogate: … signed agreement │
bob    ▸ [Remember]
bot    ▸ Got it. I'll use "active surrogate" in your future questions. Only you are affected.

alice  ▸ (next day) surrogates in screening
bot    ▸ [Same as a report you confirmed earlier] …         ← Alice's personal example, exact match

carol, dan confirm the same SQL as alice → auto-proposed → cora (curator) approves
everyone ▸ [Verified report · checked by cora on 2026-10-22] …
```
