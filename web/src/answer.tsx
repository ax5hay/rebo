// One turn of the conversation: the question as the headline, the answer under it with its trust on the
// left edge, the data sheet, how the question was read (highlighted), and everything a person can do next.
import { useMemo, useState } from "react";
import {
  Button, Cell, Column, Dialog, Heading, Modal, ModalOverlay, Row, Table, TableBody, TableHeader,
  ToggleButton, ToggleButtonGroup, type SortDescriptor,
} from "react-aria-components";
import { call, csvUrl } from "./api";
import { useMe, useToast } from "./shell";

export type Turn = { key: string; question: string; r: any };

const TRUST: Record<string, string> = { verified: "verified", yours: "yours", adapted: "adapted", new: "new" };

export function TurnView({ t, ask, onTurn, onFix }: {
  t: Turn; ask: (q: string) => void; onTurn: (question: string, r: any) => void; onFix: (turnId: string) => void;
}) {
  const r = t.r;
  return (
    <article className="turn" aria-label={t.question}>
      <h2 className="q">{t.question}{r.route && r.route !== "new" && <small>{ROUTE_NOTE[r.route] ?? ""}</small>}</h2>
      {r.kind === "report" && <Report r={r} ask={ask} onTurn={onTurn} onFix={onFix} />}
      {r.kind === "clarify" && <Clarify r={r} ask={ask} />}
      {r.kind === "answer" && (
        <div className="answer yours">
          <p className="lead">{r.text}</p>
          {r.cites?.length > 0 && <p className="small soft">From what you and your team taught: {r.cites.map((c: any) => c.title).join(", ")}</p>}
          <Suggestions items={r.suggestions} />
        </div>
      )}
      {r.kind === "error" && <div className="answer error"><p className="trust">Not answered</p><p className="lead">{r.message}</p></div>}
    </article>
  );
}

const ROUTE_NOTE: Record<string, string> = {
  direct: "Your saved report, run again with today's data. No model was asked.",
  cache: "Same question as before, run again with today's data. No model was asked.",
  params: "Your saved report with the new values filled in.",
  reuse: "Adapted from a saved report.",
  rerun: "Run again with today's data.",
  drill: "The records behind a number.",
};

function Report({ r, ask, onTurn, onFix }: { r: any; ask: (q: string) => void; onTurn: (q: string, r: any) => void; onFix: (id: string) => void }) {
  const me = useMe();
  const toast = useToast();
  const [feedback, setFeedback] = useState<string | null>(r.feedback ?? null);
  const [dialog, setDialog] = useState<null | "fix" | "schedule">(null);
  const grouped = /\bgroup\s+by\b/i.test(r.sql);
  const trust = TRUST[r.provenance?.label] ?? "new";

  const act = async (fn: () => Promise<any>) => {
    try {
      const res = await fn();
      if (res?.message) toast(res.message);
      return res;
    } catch (e) {
      toast((e as Error).message);
    }
  };

  return (
    <div className={`answer ${trust}`} data-testid="report">
      <p className="trust">{r.provenance?.text}</p>
      <p className="lead">{r.message}</p>
      <DataSheet columns={r.columns} rows={r.rows} label={r.title}
                 onRowAction={grouped ? async (i) => {
                   const res = await act(() => call("POST", `/turns/${r.turn_id}/drill`, { row: i }));
                   if (res?.kind) onTurn(`What is behind row ${i + 1} of “${r.title}”`, res);
                 } : undefined} />
      <div className="sheetfoot">
        <span>{r.rows.length} rows{r.truncated ? " shown; there are more" : ""}</span>
        {grouped && <span>Choose a row to see the records behind it.</span>}
      </div>
      <Reading items={r.assumptions} />
      <details><summary>Show the query</summary><pre className="sql">{r.sql}</pre></details>
      {r.follow_ups?.length > 0 && (
        <div className="row" style={{ marginTop: 10 }}>
          {r.follow_ups.map((f: string) => <button key={f} className="chip" onClick={() => ask(f)}>{f}</button>)}
        </div>
      )}
      <div className="actionsline">
        {feedback ? (
          <>
            <span className="verdict">{feedback === "correct" ? "You confirmed this." : "You asked for a fix."}</span>
            <button className="btn quiet" onClick={async () => { if (await act(() => call("DELETE", `/turns/${r.turn_id}/feedback`))) setFeedback(null); }}>Undo my feedback</button>
          </>
        ) : (
          <>
            <span className="verdict">Is this right?</span>
            <button className="btn" onClick={async () => { if (await act(() => call("POST", `/turns/${r.turn_id}/feedback`, { verdict: "correct" }))) setFeedback("correct"); }}>Yes, this is right</button>
            <button className="btn" onClick={() => { onFix(r.turn_id); setFeedback("wrong"); }}>No, fix it</button>
          </>
        )}
        <span className="sep" aria-hidden />
        <button className="btn quiet" onClick={async () => { const res = await act(() => call("POST", `/turns/${r.turn_id}/rerun`)); if (res?.kind) onTurn(`${r.title}, today`, res); }}>Run again with today's data</button>
        <button className="btn quiet" onClick={() => act(async () => { await call("POST", `/turns/${r.turn_id}/pin`); return { message: "Pinned. It now opens your start page." }; })}>Pin</button>
        <button className="btn quiet" onClick={() => setDialog("schedule")}>Send me this regularly</button>
        <a className="btn quiet" href={csvUrl(r.turn_id)} download>Download CSV</a>
        <button className="btn quiet" onClick={() => setDialog("fix")}>Ask an admin to fix</button>
        {me?.is_admin && r.trace_id && <TraceLink traceId={r.trace_id} />}
      </div>
      <Suggestions items={r.suggestions} />
      {dialog === "fix" && <RequestFix turnId={r.turn_id} close={() => setDialog(null)} />}
      {dialog === "schedule" && <Schedule turnId={r.turn_id} close={() => setDialog(null)} />}
    </div>
  );
}

export function Reading({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <section className="reading" aria-label="How I read your question">
      <h3>How I read your question</h3>
      <ol>
        {items.map((a) => <li key={a} className={a.startsWith("Check:") ? "check" : ""}><mark>{a}</mark></li>)}
      </ol>
    </section>
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
  return (
    <div className="sheet">
      <Table aria-label={label} sortDescriptor={sort} onSortChange={setSort}
             onRowAction={onRowAction ? (key) => onRowAction(Number(key)) : undefined}>
        <TableHeader>
          {columns.map((c, i) => <Column key={i} id={String(i)} isRowHeader={i === 0} allowsSorting className={numeric[i] ? "num" : undefined}>{c}</Column>)}
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
    <div className="answer new" data-testid="clarify">
      <p className="trust">{r.intro}</p>
      <p className="lead">{r.why}</p>
      {r.questions.map((q: any) => (
        <div key={q.question} style={{ margin: "12px 0" }}>
          <p style={{ fontWeight: 700, margin: "0 0 6px" }}>{q.question}</p>
          <ToggleButtonGroup aria-label={q.question} selectionMode="single" className="row"
                             selectedKeys={picked[q.question] ? [picked[q.question]] : []}
                             onSelectionChange={(keys) => { const k = [...keys][0]; if (k) setPicked({ ...picked, [q.question]: String(k) }); }}>
            {q.options.map((o: string) => <ToggleButton key={o} id={o} className="chip">{o}</ToggleButton>)}
          </ToggleButtonGroup>
        </div>
      ))}
      <button className="btn primary" disabled={!ready} onClick={send}>Run this</button>
      <p className="small soft">Or type your own answer below.</p>
    </div>
  );
}

export function Suggestions({ items }: { items?: any[] }) {
  const [done, setDone] = useState<Record<string, string>>({});
  if (!items?.length) return null;
  return (
    <>
      {items.map((s) => (
        <div key={s.id} className="note remember" data-testid="remember">
          <p style={{ margin: 0 }}><b>Remember this for next time?</b> “{s.title}”: {s.body}</p>
          {done[s.id] ? <p className="small" style={{ margin: "6px 0 0" }}>{done[s.id]}</p> : (
            <div className="row" style={{ marginTop: 8 }}>
              <button className="btn" onClick={async () => setDone({ ...done, [s.id]: (await call("POST", `/suggestions/${s.id}`, { accept: true })).message })}>Remember, only for me</button>
              <button className="btn quiet" onClick={async () => setDone({ ...done, [s.id]: (await call("POST", `/suggestions/${s.id}`, { accept: false })).message })}>Not now</button>
            </div>
          )}
        </div>
      ))}
    </>
  );
}

function TraceLink({ traceId }: { traceId: string }) {
  const toast = useToast();
  return (
    <button className="btn quiet" onClick={async () => {
      try {
        const { url } = await call<{ url: string }>("GET", `/trace/${traceId}`);
        window.open(url, "_blank", "noopener");
      } catch (e) {
        toast((e as Error).message);
      }
    }}>Open trace</button>
  );
}

export function Sheet({ title, close, children }: { title: string; close: () => void; children: React.ReactNode }) {
  return (
    <ModalOverlay className="overlay" isOpen isDismissable onOpenChange={(open) => !open && close()}>
      <Modal>
        <Dialog className="dialog">
          <Heading slot="title" className="h2" style={{ marginTop: 0 }}>{title}</Heading>
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
    <Sheet title="Ask an admin to fix this report" close={close}>
      <p className="soft">Say what is wrong in your own words. An admin sees it with this report attached.</p>
      <textarea className="input" rows={4} aria-label="What should change" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="row" style={{ marginTop: 12 }}>
        <Button className="btn primary" isDisabled={!text.trim()} onPress={async () => {
          try { toast((await call("POST", "/requests", { kind: "fix_report", text, turn_id: turnId })).message); close(); }
          catch (e) { toast((e as Error).message); }
        }}>Send to an admin</Button>
        <Button className="btn quiet" onPress={close}>Cancel</Button>
      </div>
    </Sheet>
  );
}

function Schedule({ turnId, close }: { turnId: string; close: () => void }) {
  const toast = useToast();
  const [day, setDay] = useState("monday");
  const [time, setTime] = useState("08:00");
  return (
    <Sheet title="Send me this regularly" close={close}>
      <p className="soft">The same query runs again with that day's data. No model is asked, so it costs nothing.</p>
      <div className="row">
        <select className="input" style={{ maxWidth: 200 }} aria-label="Day" value={day} onChange={(e) => setDay(e.target.value)}>
          <option value="daily">Every day</option>
          <option value="weekdays">Every weekday</option>
          {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((d) =>
            <option key={d} value={d}>Every {d[0].toUpperCase() + d.slice(1)}</option>)}
        </select>
        <input className="input" style={{ maxWidth: 120 }} type="time" aria-label="Time" value={time} onChange={(e) => setTime(e.target.value)} />
        <Button className="btn primary" onPress={async () => {
          try { await call("POST", "/schedules", { turn_id: turnId, every: `${day} ${time}` }); toast(`Scheduled: ${day} at ${time}.`); close(); }
          catch (e) { toast((e as Error).message); }
        }}>Schedule</Button>
      </div>
    </Sheet>
  );
}
