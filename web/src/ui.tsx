// Shared building blocks for the internal pages, so Knowledge, Review, Admin, Insights, Configuration,
// You and Help share one structure: a page head (title, one-line purpose, actions, a strip of numbers),
// section heads, empty states that say what to do next, kind icons, an overflow menu and a timeline.
import { Glass } from "./glass";
import { BookMarked, BookOpenText, GitMerge, Lightbulb, MoreHorizontal, ScrollText, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Button, Menu, MenuItem, MenuTrigger, Popover, Separator } from "react-aria-components";
import { when } from "./api";
import { Md } from "./md";

export function PageHead({ title, lede, actions, stats }: {
  title: string; lede?: ReactNode; actions?: ReactNode; stats?: { n: ReactNode; label: string; tone?: "ok" | "warn" | "bad" }[];
}) {
  return (
    <header className="pagehead">
      <div className="pagehead-top">
        <div className="pagehead-text">
          <h1>{title}</h1>
          {lede && <p className="lede">{lede}</p>}
        </div>
        {actions && <div className="pagehead-actions">{actions}</div>}
      </div>
      {stats && stats.length > 0 && (
        <dl className="statstrip">
          {stats.map((s) => <div key={s.label} className={s.tone ?? ""}><dt>{s.label}</dt><dd>{s.n}</dd></div>)}
        </dl>
      )}
    </header>
  );
}

export function SectionHead({ id, title, sub, actions }: { id?: string; title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="section-title" id={id}>
      <h2>{title}</h2>{sub !== undefined && <p>{sub}</p>}
      {actions && <><span className="spacer" /><div className="row">{actions}</div></>}
    </div>
  );
}

export function Empty({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="emptystate">
      <span className="emptyicon"><Icon /></span>
      <b>{title}</b>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export const KINDS: Record<string, { label: string; one: string; icon: LucideIcon; tone: string }> = {
  example: { label: "Saved report", one: "A question and the query that answers it", icon: ScrollText, tone: "green" },
  term: { label: "Meaning of a word", one: "What a word means in your data", icon: BookOpenText, tone: "indigo" },
  note: { label: "Rule or fact", one: "Something that is always true", icon: Lightbulb, tone: "brass" },
  join: { label: "How tables connect", one: "Which columns link two tables", icon: GitMerge, tone: "slate" },
};

export function KindIcon({ kind, size = 36 }: { kind: string; size?: number }) {
  const k = KINDS[kind] ?? { icon: BookMarked, tone: "slate" };
  return <span className={`kindicon ${k.tone}`} style={{ width: size, height: size }} aria-hidden><k.icon /></span>;
}

export type MenuAction = { id: string; label: string; icon?: LucideIcon; danger?: boolean; separator?: boolean };

export function MoreMenu({ label, actions, onAction }: { label: string; actions: MenuAction[]; onAction: (id: string) => void }) {
  if (!actions.length) return null;
  return (
    <MenuTrigger>
      <Button className="btn icon ghost" aria-label={label}><MoreHorizontal /></Button>
      <Popover placement="bottom end" offset={6} className="glasspop">
        <Glass className="menuglass" strength={24}>
          <Menu className="menu" onAction={(k) => onAction(String(k))}>
            {actions.flatMap((a) => [
              ...(a.separator ? [<Separator key={`${a.id}-sep`} />] : []),
              <MenuItem key={a.id} id={a.id} className={a.danger ? "danger" : undefined}>{a.icon && <a.icon />}{a.label}</MenuItem>,
            ])}
          </Menu>
        </Glass>
      </Popover>
    </MenuTrigger>
  );
}

const ACTION_WORDS: Record<string, string> = {
  created: "Created", edited: "Edited", confirmed: "Confirmed by someone", reported_wrong: "Reported wrong",
  pinned: "Pinned", unpinned: "Unpinned", "status:verified": "Shared with everyone", "status:retired": "Withdrawn",
  "status:stale": "Needs a re-check after a database change", "status:active": "Yours only again",
  "status:proposed": "Proposed for sharing", "status:team": "Shared with the team",
};
const say = (a: string) => ACTION_WORDS[a] ?? (a.startsWith("undo:") ? `Undone: ${(ACTION_WORDS[a.slice(5)] ?? a.slice(5)).toLowerCase()}` : a.replace("status:", "Now "));

export function Timeline({ events }: { events: any[] }) {
  if (!events.length) return <p className="muted">No changes yet.</p>;
  return (
    <ol className="timeline">
      {events.map((e) => (
        <li key={e.id}>
          <span className="tdot" aria-hidden />
          <div>
            <div className="tline"><b>{say(e.action)}</b><span className="muted small">{when(e.at)}</span></div>
            <div className="muted small">by {e.actor}{e.note ? <>: <Md inline>{e.note}</Md></> : null}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}
