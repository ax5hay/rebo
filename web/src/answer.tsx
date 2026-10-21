// One turn: the person's question, then the answer panel. Trust (verified / yours / adapted / new) is
// the first thing on the panel; the data follows; then how the question was read, as plain steps
// generated from the query itself plus the assumptions the model made.
import {
  Check, ChevronRight, Code2, Download, ExternalLink, Flag, MoreHorizontal, Pencil, Pin, RotateCcw, Timer, Undo2,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Button, Cell, Column, Dialog, Heading, Menu, MenuItem, MenuTrigger, Modal, ModalOverlay, Popover, Row, Separator,
  Table, TableBody, TableHeader, ToggleButton, ToggleButtonGroup, type SortDescriptor,
} from "react-aria-components";
import { call, csvUrl, plural } from "./api";
import { useMe, useToast } from "./shell";
import { Md } from "./md";

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
  const [feedback, setFeedback] = useState<string | null>(r.feedback ?? null);
  const [dialog, setDialog] = useState<null | "fix" | "schedule">(null);
  const grouped = /\bgroup\s+by\b/i.test(r.sql);
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

  return (
    <section className="panel answer" data-testid="report">
      <header className="answer-head">
        <span className={`pill ${label}`} title={r.provenance?.text}><span className="dot" />{PILL[label] ?? "New"}</span>
        <span className="title">{r.title}</span>
        <span className="meta">{plural(r.rows.length, "row", "rows")}{r.truncated ? "+" : ""}{r.elapsed_ms ? `, ${r.elapsed_ms} ms` : ""}</span>
        <span className="spacer" />
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
          <Button className="btn ghost icon" aria-label="More actions"><MoreHorizontal /></Button>
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
      </header>
      {r.route && ROUTE_NOTE[r.route] && <p className="answer-note">{ROUTE_NOTE[r.route]}</p>}
      <DataSheet columns={r.columns} rows={r.rows} label={r.title}
                 onRowAction={grouped ? async (i) => {
                   const res = await act(() => call("POST", `/turns/${r.turn_id}/drill`, { row: i }));
                   if (res?.kind) onTurn(`The records behind row ${i + 1} of “${r.title}”`, res);
                 } : undefined} />
      <div className="table-foot">
        <span><Md inline>{r.provenance?.text}</Md></span>
        {grouped && <span>Select a row to see the records behind it.</span>}
      </div>
      <Reading steps={r.steps} assumptions={r.assumptions} sql={r.sql} />
      {r.follow_ups?.length > 0 && (
        <div className="followups">
          {r.follow_ups.map((f: string) => <button key={f} className="chip" onClick={() => ask(f)}>{f}</button>)}
        </div>
      )}
      <Suggestions items={r.suggestions} />
      {dialog === "fix" && <RequestFix turnId={r.turn_id} close={() => setDialog(null)} />}
      {dialog === "schedule" && <Schedule turnId={r.turn_id} close={() => setDialog(null)} />}
    </section>
  );
}

export function Reading({ steps, assumptions, sql }: { steps?: string[]; assumptions: string[]; sql: string }) {
  return (
    <div className="reading">
      {steps && steps.length > 0 && (
        <div>
          <h3>What the query does</h3>
          <ol className="steps">{steps.map((s, i) => <li key={i}><Md inline>{s}</Md></li>)}</ol>
        </div>
      )}
      {assumptions?.length > 0 && (
        <div>
          <h3>How I read your question</h3>
          <ul className="assumptions">
            {assumptions.map((a) => <li key={a} className={a.startsWith("Check:") ? "check" : ""}><mark><Md inline>{a}</Md></mark></li>)}
          </ul>
        </div>
      )}
      <details className="query">
        <summary><Code2 size={14} />Show the query<ChevronRight size={14} /></summary>
        <pre className="code">{sql}</pre>
      </details>
    </div>
  );
}

export function DataSheet({ columns, rows, label, onRowAction }: {
  columns: string[]; rows: any[][]; label: string; onRowAction?: (index: number) => void;
}) {
  const [sort, setSort] = useState<SortDescriptor | undefined>();
  const items = useMemo(() => {
    const indexed = rows.map((row, i) => ({ id: i, row }));
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
  }, [rows, sort]);
  const numeric = columns.map((_, c) => rows.length > 0 && rows.every((r) => r[c] === null || typeof r[c] === "number"));
  if (!rows.length) return <div className="empty">No rows matched.</div>;
  return (
    <div className="table-wrap">
      <Table className="data" aria-label={label} sortDescriptor={sort} onSortChange={setSort}
             onRowAction={onRowAction ? (key) => onRowAction(Number(key)) : undefined}>
        <TableHeader>
          {columns.map((c, i) => <Column key={i} id={String(i)} isRowHeader={i === 0} allowsSorting className={numeric[i] ? "num" : undefined}>{c.replaceAll("_", " ")}</Column>)}
        </TableHeader>
        <TableBody items={items}>
          {(item) => (
            <Row id={item.id} className={onRowAction ? "clickable" : undefined}>
              {item.row.map((v: any, j: number) => <Cell key={j} className={numeric[j] ? "num" : undefined}>{v === null ? "" : String(v)}</Cell>)}
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
      <header className="answer-head"><span className="pill yours"><span className="dot" />One question first</span><span className="title"><Md inline>{r.why}</Md></span></header>
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

export function Sheet({ title, intro, close, children }: { title: string; intro?: string; close: () => void; children: React.ReactNode }) {
  return (
    <ModalOverlay className="overlay" isOpen isDismissable onOpenChange={(open) => !open && close()}>
      <Modal>
        <Dialog className="dialog">
          <Heading slot="title">{title}</Heading>
          {intro && <p className="muted" style={{ marginTop: 4 }}>{intro}</p>}
          {children}
        </Dialog>
      </Modal>
    </ModalOverlay>
  );
}

function RequestFix({ turnId, close }: { turnId: string; close: () => void }) {
  const toast = useToast();
  const [text, setText] = useState("");
  return (
    <Sheet title="Ask an admin to fix this report" intro="Say what is wrong in your own words. An admin sees it with this report attached." close={close}>
      <textarea className="textarea" rows={4} aria-label="What should change" value={text} onChange={(e) => setText(e.target.value)} autoFocus />
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

function Schedule({ turnId, close }: { turnId: string; close: () => void }) {
  const toast = useToast();
  const [day, setDay] = useState("monday");
  const [time, setTime] = useState("08:00");
  return (
    <Sheet title="Send me this regularly" intro="The same query runs again on that day's data. No model is asked, so it costs nothing." close={close}>
      <div className="row" style={{ marginTop: 12 }}>
        <select className="select" style={{ maxWidth: 220 }} aria-label="Day" value={day} onChange={(e) => setDay(e.target.value)}>
          <option value="daily">Every day</option>
          <option value="weekdays">Every weekday</option>
          {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((d) =>
            <option key={d} value={d}>Every {d[0].toUpperCase() + d.slice(1)}</option>)}
        </select>
        <input className="input" style={{ maxWidth: 130 }} type="time" aria-label="Time" value={time} onChange={(e) => setTime(e.target.value)} />
      </div>
      <div className="actions">
        <Button className="btn ghost" onPress={close}>Cancel</Button>
        <Button className="btn primary" onPress={async () => {
          try { await call("POST", "/schedules", { turn_id: turnId, every: `${day} ${time}` }); toast(`Scheduled: ${day} at ${time}.`); close(); }
          catch (e) { toast((e as Error).message); }
        }}>Schedule</Button>
      </div>
    </Sheet>
  );
}
