// One turn: the person's question, then the answer panel, built to be scanned: trust label and title,
// one line of facts (rows, time, choices made, things to check), the data with its tools, then how the
// question was read and what the query does, each foldable.
import {
  BarChart3, Check, ChevronRight, CircleCheck, Code2, Copy, Download, ExternalLink, Flag, MoreHorizontal, MousePointerClick, Pencil, Pin,
  RotateCcw, Search, Table as TableIcon, Timer, TriangleAlert, Undo2, X, type LucideIcon,
} from "lucide-react";
import { lazy, Suspense, useMemo, useState } from "react";
import {
  Button, Cell, Column, Dialog, Heading, Menu, MenuItem, MenuTrigger, Modal, ModalOverlay, Popover, Row, Separator,
  Table, TableBody, TableHeader, ToggleButton, ToggleButtonGroup, type SortDescriptor,
} from "react-aria-components";
import { call, csvUrl, plural } from "./api";
import { usePrefs } from "./prefs";
import { useMe, useToast } from "./shell";
import { Md } from "./md";
import { SqlCode } from "./code";
import { chartShape } from "./chart";
const ResultChart = lazy(() => import("./chart"));

export type Turn = { key: string; question: string; r: any };

const ROUTE_NOTE: Record<string, string> = {
  direct: "Your saved report, run again on today's data. No model was asked.",
  cache: "Same question as before, run again on today's data. No model was asked.",
  params: "Your saved report with the new values filled in.",
  reuse: "Adapted from a saved report.",
  rerun: "Run again on today's data.",
  drill: "The records behind a number.",
};
const PILL: Record<string, string> = { verified: "Verified", yours: "Your report", adapted: "From saved knowledge", new: "New" };

export function TurnView({ t, ask, onTurn, onFix, initial }: {
  t: Turn; ask: (q: string) => void; onTurn: (question: string, r: any) => void; onFix: (turnId: string) => void; initial: string;
}) {
  const r = t.r;
  return (
    <article aria-label={t.question}>
      <div className="ask" style={{ marginBottom: 12 }}>
        <span className="avatar" aria-hidden>{initial}</span>
        <div className="text">{t.question}</div>
      </div>
      {r.kind === "report" && <Report r={r} ask={ask} onTurn={onTurn} onFix={onFix} />}
      {r.kind === "clarify" && <Clarify r={r} ask={ask} />}
      {r.kind === "answer" && (
        <section className="panel answer">
          <div className="answer-body" style={{ paddingTop: 14 }}>
            <Md className="reply">{r.text}</Md>
            {r.cites?.length > 0 && <p className="small muted" style={{ marginBottom: 0 }}>Based on: {r.cites.map((c: any) => c.title).join(", ")}</p>}
          </div>
          <Suggestions items={r.suggestions} />
        </section>
      )}
      {r.kind === "error" && (
        <section className="panel answer">
          <div className="answer-head"><span className="pill danger"><span className="dot" />Not answered</span></div>
          <div className="answer-body"><Md>{r.message}</Md></div>
        </section>
      )}
    </article>
  );
}

function Report({ r, ask, onTurn, onFix }: { r: any; ask: (q: string) => void; onTurn: (q: string, r: any) => void; onFix: (id: string) => void }) {
  const me = useMe();
  const toast = useToast();
  const prefs = usePrefs();
  const [feedback, setFeedback] = useState<string | null>(r.feedback ?? null);
  const [dialog, setDialog] = useState<null | "fix" | "schedule">(null);
  const grouped = /\bgroup\s+by\b/i.test(r.sql);
  const chartable = useMemo(() => chartShape(r.columns, r.rows, r.sql) !== null, [r.columns, r.rows, r.sql]);
  const [view, setView] = useState<"table" | "chart">(chartable && prefs.chartFirst ? "chart" : "table");
  const [filter, setFilter] = useState("");
  const label = r.provenance?.label ?? "new";
  const act = async (fn: () => Promise<any>) => {
    try { const res = await fn(); if (res?.message) toast(res.message); return res; }
    catch (e) { toast((e as Error).message); }
  };
  const menu = async (key: string) => {
    if (key === "rerun") { const res = await act(() => call("POST", `/turns/${r.turn_id}/rerun`)); if (res?.kind) onTurn(`${r.title}, today`, res); }
    if (key === "pin") await act(async () => { await call("POST", `/turns/${r.turn_id}/pin`); return { message: "Pinned. It now opens your start page." }; });
    if (key === "schedule") setDialog("schedule");
    if (key === "csv") window.location.assign(csvUrl(r.turn_id));
    if (key === "fix") setDialog("fix");
    if (key === "trace") {
      try { const { url } = await call<{ url: string }>("GET", `/trace/${r.trace_id}`); window.open(url, "_blank", "noopener"); }
      catch (e) { toast((e as Error).message); }
    }
  };
  const copy = async () => {
    const tsv = [r.columns.join("\t"), ...r.rows.map((row: any[]) => row.map((v) => (v === null ? "" : String(v))).join("\t"))].join("\n");
    try { await navigator.clipboard.writeText(tsv); toast(`Copied ${plural(r.rows.length, "row", "rows")}. Paste into a spreadsheet.`); }
    catch { toast("Copying is blocked in this browser. Use Download CSV."); }
  };
  const checks = (r.assumptions ?? []).filter((a: string) => a.startsWith("Check:")).length;

  return (
    <section className="panel answer" data-testid="report">
      <header className="answer-head">
        <div className="headline">
          <span className={`pill ${label}`} title={r.provenance?.text}><span className="dot" />{PILL[label] ?? "New"}</span>
          <h3 className="title">{r.title}</h3>
        </div>
        <div className="actions">
          {feedback ? (
            <>
              <span className={`pill ${feedback === "correct" ? "verified" : "warn"}`}>{feedback === "correct" ? "You confirmed this" : "You asked for a fix"}</span>
              <button className="btn ghost" onClick={async () => { if (await act(() => call("DELETE", `/turns/${r.turn_id}/feedback`))) setFeedback(null); }}><Undo2 />Undo my feedback</button>
            </>
          ) : (
            <>
              <button className="btn good" onClick={async () => { if (await act(() => call("POST", `/turns/${r.turn_id}/feedback`, { verdict: "correct" }))) setFeedback("correct"); }}><Check />Yes, this is right</button>
              <button className="btn fix" onClick={() => { onFix(r.turn_id); setFeedback("wrong"); }}><Pencil />No, fix it</button>
            </>
          )}
          <MenuTrigger>
            <Button className="btn icon" aria-label="More actions"><MoreHorizontal /></Button>
            <Popover placement="bottom end" offset={6}>
              <Menu className="menu" onAction={(k) => menu(String(k))}>
                <MenuItem id="rerun"><RotateCcw />Run again on today's data</MenuItem>
                <MenuItem id="schedule"><Timer />Send me this regularly</MenuItem>
                <MenuItem id="pin"><Pin />Pin to my start page</MenuItem>
                <MenuItem id="csv"><Download />Download CSV</MenuItem>
                <Separator />
                <MenuItem id="fix"><Flag />Ask an admin to fix this</MenuItem>
                {me?.is_admin && r.trace_id ? <MenuItem id="trace"><ExternalLink />Open the trace</MenuItem> : null}
              </Menu>
            </Popover>
          </MenuTrigger>
        </div>
      </header>
      <ul className="facts" aria-label="About this answer">
        <li><b>{r.rows.length.toLocaleString()}{r.truncated ? "+" : ""}</b> {r.rows.length === 1 ? "row" : "rows"}</li>
        {r.elapsed_ms ? <li><b>{r.elapsed_ms}</b> ms</li> : null}
        {r.assumptions?.length > 0 && <li><b>{r.assumptions.length}</b> {r.assumptions.length === 1 ? "choice made" : "choices made"}</li>}
        {checks > 0 && <li className="warn"><b>{checks}</b> to check</li>}
        {r.route && ROUTE_NOTE[r.route] && <li className="route">{ROUTE_NOTE[r.route]}</li>}
      </ul>
      <div className="tabletools">
        {chartable && (
          <ToggleButtonGroup aria-label="Show as" selectionMode="single" disallowEmptySelection selectedKeys={[view]} className="segmented small"
                             onSelectionChange={(k) => setView([...k][0] as "table" | "chart")}>
            <ToggleButton id="table"><TableIcon size={14} />Table</ToggleButton>
            <ToggleButton id="chart"><BarChart3 size={14} />Chart</ToggleButton>
          </ToggleButtonGroup>
        )}
        {view === "table" && r.rows.length > 8 && (
          <label className="filter"><Search /><input aria-label="Filter these rows" placeholder="Filter these rows" value={filter} onChange={(e) => setFilter(e.target.value)} /></label>
        )}
        <span className="spacer" />
        <button className="btn ghost small" onClick={copy}><Copy />Copy</button>
        <a className="btn ghost small" href={csvUrl(r.turn_id)}><Download />CSV</a>
      </div>
      {view === "chart" && chartable ? <Suspense fallback={<div className="empty">Drawing…</div>}><ResultChart columns={r.columns} rows={r.rows} sql={r.sql} /></Suspense> :
      <DataSheet columns={r.columns} rows={r.rows} label={r.title} filter={filter}
                 onRowAction={grouped ? async (i) => {
                   const res = await act(() => call("POST", `/turns/${r.turn_id}/drill`, { row: i }));
                   if (res?.kind) onTurn(`The records behind row ${i + 1} of “${r.title}”`, res);
                 } : undefined} />}
      <div className="table-foot">
        <span><Md inline>{r.provenance?.text}</Md></span>
        {grouped && view === "table" && <span><MousePointerClick size={13} />Select a row to see the records behind it</span>}
      </div>
      <Reading steps={r.steps} assumptions={r.assumptions} sql={r.sql} />
      {r.follow_ups?.length > 0 && (
        <div className="followups">
          <span className="label">Ask next</span>
          {r.follow_ups.map((f: string) => <button key={f} className="chip" onClick={() => ask(f)}>{f}</button>)}
        </div>
      )}
      <Suggestions items={r.suggestions} />
      {dialog === "fix" && <RequestFix turnId={r.turn_id} close={() => setDialog(null)} />}
      {dialog === "schedule" && <Schedule turnId={r.turn_id} close={() => setDialog(null)} />}
    </section>
  );
}

// "How I read your question" first: it is what decides whether the numbers answer the question asked.
// Each choice is its own line; a "Check:" line (the reviewer's doubt) is set apart in amber.
export function Reading({ steps, assumptions, sql }: { steps?: string[]; assumptions: string[]; sql: string }) {
  const prefs = usePrefs();
  const list = assumptions ?? [];
  const checks = list.filter((a) => a.startsWith("Check:"));
  const choices = list.filter((a) => !a.startsWith("Check:"));
  return (
    <div className="reading">
      {list.length > 0 && (
        <details className="readas" open={prefs.reading === "open"}>
          <summary><h4>How I read your question</h4><span className="count">{plural(choices.length, "choice", "choices")}{checks.length ? `, ${checks.length} to check` : ""}</span><ChevronRight size={15} /></summary>
          <ul>
            {checks.map((a) => <li key={a} className="check"><TriangleAlert /><Md inline>{a.replace(/^Check:\s*/, "")}</Md></li>)}
            {choices.map((a) => <li key={a}><CircleCheck /><Md inline>{a}</Md></li>)}
          </ul>
        </details>
      )}
      {steps && steps.length > 0 && (
        <details className="stepsbox" open={prefs.reading === "open"}>
          <summary><h4>What the query does</h4><span className="count">{plural(steps.length, "step", "steps")}</span><ChevronRight size={15} /></summary>
          <ol className="steps">{steps.map((s, i) => <li key={i}><Md inline>{s}</Md></li>)}</ol>
        </details>
      )}
      <details className="query">
        <summary><Code2 size={14} />Show the query<ChevronRight size={14} /></summary>
        <SqlCode sql={sql} />
      </details>
    </div>
  );
}

const ID_COLUMN = /(^|_)(id|code|number|no|year|zip|postcode|phone)$/i;
const fmt = (v: any, plain: boolean) =>
  v === null ? "" : typeof v === "number" && !plain ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v);

export function DataSheet({ columns, rows, label, onRowAction, filter = "" }: {
  columns: string[]; rows: any[][]; label: string; onRowAction?: (index: number) => void; filter?: string;
}) {
  const [sort, setSort] = useState<SortDescriptor | undefined>();
  const items = useMemo(() => {
    const f = filter.trim().toLowerCase();
    const indexed = rows.map((row, i) => ({ id: i, row })).filter((x) => !f || x.row.some((v) => v !== null && String(v).toLowerCase().includes(f)));
    if (!sort) return indexed;
    const c = Number(sort.column);
    const dir = sort.direction === "descending" ? -1 : 1;
    return [...indexed].sort((a, b) => {
      const x = a.row[c], y = b.row[c];
      if (x === y) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * dir;
    });
  }, [rows, sort, filter]);
  const numeric = columns.map((_, c) => rows.length > 0 && rows.every((r) => r[c] === null || typeof r[c] === "number"));
  const plain = columns.map((c) => ID_COLUMN.test(c));
  if (!rows.length) return <div className="empty">No rows matched.</div>;
  return (
    <div className="table-wrap">
      <Table className="data" aria-label={label} sortDescriptor={sort} onSortChange={setSort}
             onRowAction={onRowAction ? (key) => onRowAction(Number(key)) : undefined}>
        <TableHeader>
          {columns.map((c, i) => <Column key={i} id={String(i)} isRowHeader={i === 0} allowsSorting className={numeric[i] ? "num" : undefined}>{c.replaceAll("_", " ")}</Column>)}
        </TableHeader>
        <TableBody items={items} renderEmptyState={() => <div className="empty">No row contains “{filter}”.</div>}>
          {(item) => (
            <Row id={item.id} className={onRowAction ? "clickable" : undefined}>
              {item.row.map((v: any, j: number) => <Cell key={j} className={numeric[j] ? "num" : undefined}>{fmt(v, plain[j])}</Cell>)}
            </Row>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function Clarify({ r, ask }: { r: any; ask: (q: string) => void }) {
  const [picked, setPicked] = useState<Record<string, string>>({});
  const ready = r.questions.every((q: any) => picked[q.question]);
  const send = () => ask(r.questions.length === 1 ? picked[r.questions[0].question]
    : r.questions.map((q: any) => `${q.question} → ${picked[q.question]}`).join("; "));
  return (
    <section className="panel answer" data-testid="clarify">
      <header className="answer-head"><div className="headline"><span className="pill yours"><span className="dot" />One question first</span><h3 className="title"><Md inline>{r.why}</Md></h3></div></header>
      <div className="answer-body">
        {r.questions.map((q: any) => (
          <div key={q.question} style={{ marginBottom: 14 }}>
            <p style={{ fontWeight: 600, margin: "0 0 8px" }}><Md inline>{q.question}</Md></p>
            <ToggleButtonGroup aria-label={q.question} selectionMode="single" className="row"
                               selectedKeys={picked[q.question] ? [picked[q.question]] : []}
                               onSelectionChange={(keys) => { const k = [...keys][0]; if (k) setPicked({ ...picked, [q.question]: String(k) }); }}>
              {q.options.map((o: string) => <ToggleButton key={o} id={o} className="chip">{o}</ToggleButton>)}
            </ToggleButtonGroup>
          </div>
        ))}
        <div className="row"><button className="btn primary" disabled={!ready} onClick={send}>Run this</button><span className="small muted">or type your own answer below</span></div>
      </div>
    </section>
  );
}

export function Suggestions({ items }: { items?: any[] }) {
  const [done, setDone] = useState<Record<string, string>>({});
  if (!items?.length) return null;
  return (
    <>
      {items.map((s) => (
        <div key={s.id} className="callout" data-testid="remember">
          <div className="grow"><b>Remember this for next time?</b> “{s.title}”: <Md inline>{s.body}</Md></div>
          {done[s.id] ? <span className="small">{done[s.id]}</span> : (
            <div className="row">
              <button className="btn" onClick={async () => setDone({ ...done, [s.id]: (await call("POST", `/suggestions/${s.id}`, { accept: true })).message })}>Remember, only for me</button>
              <button className="btn ghost" onClick={async () => setDone({ ...done, [s.id]: (await call("POST", `/suggestions/${s.id}`, { accept: false })).message })}>Not now</button>
            </div>
          )}
        </div>
      ))}
    </>
  );
}

export function Sheet({ title, intro, close, children, icon: Icon, wide }: {
  title: string; intro?: string; close: () => void; children: React.ReactNode; icon?: LucideIcon; wide?: boolean;
}) {
  return (
    <ModalOverlay className="overlay" isOpen isDismissable onOpenChange={(open) => !open && close()}>
      <Modal>
        <Dialog className={`dialog${wide ? " wide" : ""}`}>
          <div className="dialoghead">
            {Icon && <span className="dialogicon"><Icon /></span>}
            <div className="grow">
              <Heading slot="title">{title}</Heading>
              {intro && <p className="muted">{intro}</p>}
            </div>
            <Button className="iconbtn" aria-label="Close" onPress={close}><X /></Button>
          </div>
          {children}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function RequestFix({ turnId, close }: { turnId: string; close: () => void }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const ideas = ["These numbers look too high", "It should leave out test accounts", "It is counting the wrong thing"];
  return (
    <Sheet icon={Flag} title="Ask an admin to fix this report" intro="Say what is wrong in your own words. An admin sees it with this report attached, and you see their answer under Knowledge → My requests." close={close}>
      <textarea className="textarea" rows={4} aria-label="What should change" placeholder="What is wrong, and what you expected" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
      <div className="chips small" aria-label="Starting points">{ideas.map((i) => <button key={i} type="button" className="chip" onClick={() => setText(i)}>{i}</button>)}</div>
      <div className="actions">
        <Button className="btn ghost" onPress={close}>Cancel</Button>
        <Button className="btn primary" isDisabled={!text.trim()} onPress={async () => {
          try { toast((await call("POST", "/requests", { kind: "fix_report", text, turn_id: turnId })).message); close(); }
          catch (e) { toast((e as Error).message); }
        }}>Send to an admin</Button>
      </div>
    </Sheet>
  );
}

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const cap = (d: string) => d[0].toUpperCase() + d.slice(1);

function Schedule({ turnId, close }: { turnId: string; close: () => void }) {
  const toast = useToast();
  const [how, setHow] = useState<"daily" | "weekdays" | "weekly">("weekly");
  const [day, setDay] = useState("monday");
  const [time, setTime] = useState("08:00");
  const every = how === "weekly" ? day : how;
  const sentence = how === "daily" ? "Every day" : how === "weekdays" ? "Every weekday" : `Every ${cap(day)}`;
  return (
    <Sheet icon={Timer} title="Send me this regularly" intro="The same query runs again on that day's data. No model is asked, so it costs nothing." close={close}>
      <div className="field"><label>How often</label>
        <ToggleButtonGroup aria-label="How often" selectionMode="single" disallowEmptySelection className="segmented" selectedKeys={[how]}
                           onSelectionChange={(k) => setHow([...k][0] as typeof how)}>
          <ToggleButton id="daily">Every day</ToggleButton><ToggleButton id="weekdays">Weekdays</ToggleButton><ToggleButton id="weekly">Once a week</ToggleButton>
        </ToggleButtonGroup>
      </div>
      {how === "weekly" && (
        <div className="field"><label>On</label>
          <ToggleButtonGroup aria-label="Day" selectionMode="single" disallowEmptySelection className="daypick" selectedKeys={[day]}
                             onSelectionChange={(k) => setDay(String([...k][0]))}>
            {DAYS.map((d) => <ToggleButton key={d} id={d} aria-label={cap(d)}>{cap(d).slice(0, 3)}</ToggleButton>)}
          </ToggleButtonGroup>
        </div>
      )}
      <div className="field"><label htmlFor="sched-time">At</label>
        <input id="sched-time" className="input" style={{ maxWidth: 140 }} type="time" value={time} onChange={(e) => setTime(e.target.value)} />
      </div>
      <p className="summaryline"><Timer />{sentence} at {time}, on that day's data.</p>
      <div className="actions">
        <Button className="btn ghost" onPress={close}>Cancel</Button>
        <Button className="btn primary" onPress={async () => {
          try { await call("POST", "/schedules", { turn_id: turnId, every: `${every} ${time}` }); toast(`Scheduled: ${sentence.toLowerCase()} at ${time}.`); close(); }
          catch (e) { toast((e as Error).message); }
        }}>Schedule it</Button>
      </div>
    </Sheet>
  );
}
