# 25 · Brand and design language

## The mark

![ReBo mark](images/logo.svg)

An **R** built from the bot's own material: the stem is a tall data bar (white), the bowl is a lens
(green, reading your question), the leg is a short report bar (brass). It reads as a letter at 16 px
and as a tiny bar chart under a lens at 64 px. One drawing everywhere: `web/public/logo.svg`
(favicon, app icon), `web/src/brand.tsx` (`Mark`, `Wordmark`), `docs/images/logo.svg`, the README
banner. Colours are fixed in both themes; on dark surfaces the tile gets a 0.5 px light edge.

| Role | Colour | Used for |
|---|---|---|
| Ink tile | `#0d1b24` | the mark's ground |
| Lens green | `#3fd0a6` (mark), `#0a7a5f` / `#3fcf9f` (UI light / dark) | trust, learning, the primary action |
| Brass | `#e6a93c` (mark), `#9c650a` / `#efbd5c` (UI) | only "how I read your question" and the AI notice |
| Indigo | `#3946c0` / `#9aa6ff` | what is yours |

Name: **ReBo** (Reports + Bot), always with a capital B. Voice: plain, short, active, the user's
words, never "AI-powered". The AI notice, in our words: "ReBo is an AI. The rows are real data, but
it can misread a question, so each answer says how it read yours."

## Liquid Glass, and where it goes beyond it (2026-10-21)

Sources: Apple HIG "Materials" and WWDC25 session 219 "Meet Liquid Glass" (lensing as the defining
property, specular highlights reacting to movement, glass only for the navigation layer floating over
content, concentric shapes, regular vs clear variants), the HIG update notes
(pxlnv.com/linklog/hig-liquid-glass), and web techniques (LogRocket "How to create Liquid Glass
effects with CSS and SVG"; ekino "Liquid glass in CSS and SVG"; WebKit bug 313914 on Safari's
missing support). Verified on primary pages: the WWDC session page; the rest are secondary.

What ReBo implements (`web/src/glass.tsx`, `web/src/styles.css` "Liquid Glass material"):

- **Lensing, computed per element.** A displacement map for each glass element's own size and corner
  radius (signed distance to a rounded rectangle, smooth bezel slope, displacement along the inward
  normal: the edge magnifies, the middle stays true), applied with `feDisplacementMap` through
  `backdrop-filter: url(#…)`. Rebuilt on resize. Chromium renders it; Safari and Firefox get the
  same material without the bend (blur, saturation, tint), which is the honest fallback.
- **Glass only on the navigation layer**: the bar islands, the sliding tab lens, the composer,
  sheets, menus, toasts, the phone tab bar. Content (answers, tables, cards) stays on solid surfaces,
  as the HIG prescribes, so text is never read through glass.
- **Scroll-edge effect**: content softens under the bar as it scrolls (a progressive blur).
- **Beyond Apple.** (1) The specular rim follows the pointer (`--lx/--ly`, animated with
  `@property`), where Apple ties it to device motion; on a desktop the pointer is the light.
  (2) Legibility, the main criticism of iOS 26: "Reduce transparency" (`prefers-reduced-transparency`)
  and the "Liquid Glass" switch on the You page turn every glass surface solid; forced colours draw a
  border. (3) Springs only on what a person did (tab lens, buttons, sheet, answer arrival); reduced
  motion turns them off.
- **Type**: the system font (SF Pro on Apple devices), Inter Variable elsewhere (OFL, self-hosted);
  SF Mono / JetBrains Mono for queries.
- **Concentric radii**: islands and chips are capsules, cards 22 px, inner boxes 16, controls 12,
  small controls 10.

## Structure

No sidebar. A floating bar of three islands: history and the wordmark; the sections, with a lens that
springs to the open one; tools (new question, ⌘K, help, you). The conversation history is a glass
sheet (⌘/). "You" is a page (profile, what your role can do, pinned and scheduled reports, shortcuts,
display preferences, local sign-in). Help is a page with a contents list, deep links to every feature
and "Try it" questions. On phones a floating tab bar replaces the section tabs.

## Readability rules for answers

- One line of facts under the title (rows, time, choices made, things to check, where it came from).
- Tables: alternate row shading (on by default), numbers right-aligned with thousands separators (id-
  like columns left raw), sticky header, filter in place, copy as TSV, CSV, comfortable or compact.
- "How I read your question" is first, each choice on its own line with a tick; a reviewer's "Check"
  line is set apart in amber at the top. Both reading boxes fold to one line (preference).
- Feedback buttons are tinted (green "Yes", amber "No") so they never blend into the panel.
