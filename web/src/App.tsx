// The Ask page (B-034): reports as cards, clarification and follow-up chips, feedback in words with
// undo, "remember this" cards and fix requests. Admin pages stay in the NiceGUI UI (/admin, /review).
import { useEffect, useRef, useState } from "react";
import { askStream, call, Step } from "./api";

type Turn = { id: string; who: "me" | "bot"; text?: string; r?: any };

const newThread = () => `conv_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;

export default function App() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [thread, setThread] = useState(newThread);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [correcting, setCorrecting] = useState<string | null>(null);
  const [starters, setStarters] = useState<string[]>([]);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => { call<string[]>("GET", "/starter").then(setStarters).catch(() => {}); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, busy]);

  async function send(message: string) {
    message = message.trim();
    if (!message || busy) return;
    const shown = message;
    if (correcting) {
      await call("POST", `/turns/${correcting}/feedback`, { verdict: "wrong", note: message }).catch(() => {});
      message = `Correction to the previous report: ${message}`;
      setCorrecting(null);
    }
    setTurns((t) => [...t, { id: crypto.randomUUID(), who: "me", text: shown }]);
    setText("");
    setBusy("Reading your question…");
    try {
      const r = await askStream(message, thread, (s: Step) => setBusy(String(s.say ?? "Working…")));
      setTurns((t) => [...t, { id: r.turn_id, who: "bot", r }]);
    } catch (e) {
      setTurns((t) => [...t, { id: crypto.randomUUID(), who: "bot", r: { kind: "error", message: String((e as Error).message) } }]);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Reports</h1>
        <button className="link" onClick={() => { setTurns([]); setThread(newThread()); }}>New conversation</button>
      </header>
      <main>
        {turns.length === 0 && (
          <div className="welcome">
            <p>Ask for a report in plain words. I show the rows, how I read your question, and where the answer came from.</p>
            {starters.length > 0 && (
              <div className="chips">
                <span className="muted">Others often ask:</span>
                {starters.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
              </div>
            )}
          </div>
        )}
        {turns.map((t) => t.who === "me"
          ? <div key={t.id} className="me">{t.text}</div>
          : <BotTurn key={t.id} r={t.r} send={send} onFix={(id) => setCorrecting(id)} />)}
        {busy && <div className="progress" role="status"><span className="spinner" />{busy}</div>}
        <div ref={end} />
      </main>
      <footer>
        {correcting && <div className="muted">What should be different? For example: “only count active ones”.</div>}
        <form onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <input aria-label="Question" value={text} onChange={(e) => setText(e.target.value)}
                 placeholder={correcting ? "Describe the correction" : "Ask for a report"} />
          <button type="submit" disabled={!!busy}>Ask</button>
        </form>
      </footer>
    </div>
  );
}

function BotTurn({ r, send, onFix }: { r: any; send: (s: string) => void; onFix: (turnId: string) => void }) {
  if (r.kind === "report") return <ReportCard r={r} send={send} onFix={onFix} />;
  if (r.kind === "clarify") return <ClarifyCard r={r} send={send} />;
  if (r.kind === "answer") {
    return (
      <div className="card">
        <p>{r.text}</p>
        {r.cites?.length > 0 && <p className="muted">From: {r.cites.map((c: any) => `${c.title} (${c.trust})`).join(", ")}</p>}
        <Suggestions items={r.suggestions} />
      </div>
    );
  }
  return <div className="card error">{r.message}</div>;
}

function ReportCard({ r, send, onFix }: { r: any; send: (s: string) => void; onFix: (turnId: string) => void }) {
  const [feedback, setFeedback] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const [asking, setAsking] = useState(false);
  const rows: any[][] = all ? r.rows : r.rows.slice(0, 25);

  async function confirm() {
    const res = await call("POST", `/turns/${r.turn_id}/feedback`, { verdict: "correct" });
    setFeedback(res.message);
  }
  async function undo() {
    const res = await call("DELETE", `/turns/${r.turn_id}/feedback`);
    setFeedback(null);
    alert(res.message);
  }
  return (
    <div className="card report" data-testid="report">
      <span className={`badge ${r.provenance?.label}`}>{r.provenance?.text}</span>
      <p className="title">{r.message}</p>
      <div className="table-wrap">
        <table>
          <thead><tr>{r.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{rows.map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{v === null ? "" : String(v)}</td>)}</tr>)}</tbody>
        </table>
      </div>
      {r.rows.length > 25 && !all && <button className="link" onClick={() => setAll(true)}>Show all {r.rows.length} rows</button>}
      <details open>
        <summary>How I read your question</summary>
        <ul>{r.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul>
      </details>
      <details><summary>Show SQL</summary><pre>{r.sql}</pre></details>
      {r.follow_ups?.length > 0 && (
        <div className="chips">{r.follow_ups.map((f: string) => <button key={f} className="chip" onClick={() => send(f)}>{f}</button>)}</div>
      )}
      <div className="row">
        {feedback ? (
          <>
            <span className="muted">{feedback}</span>
            <button className="link" onClick={undo}>Undo my feedback</button>
          </>
        ) : (
          <>
            <span>Is this right?</span>
            <button onClick={confirm}>Yes, this is right</button>
            <button onClick={() => { onFix(r.turn_id); setFeedback("Tell me what to change below."); }}>No, fix it</button>
          </>
        )}
        <span className="spacer" />
        <a className="link" href={`/api/turns/${r.turn_id}/csv${window.location.search}`}>Download CSV</a>
        <button className="link" onClick={() => setAsking(true)}>Request a fix</button>
      </div>
      {asking && <RequestFix turnId={r.turn_id} done={() => setAsking(false)} />}
      <Suggestions items={r.suggestions} />
    </div>
  );
}

function ClarifyCard({ r, send }: { r: any; send: (s: string) => void }) {
  const [picked, setPicked] = useState<Record<string, string>>({});
  const ready = r.questions.every((q: any) => picked[q.question]);
  const answer = () => send(r.questions.length === 1 ? picked[r.questions[0].question]
    : r.questions.map((q: any) => `${q.question} → ${picked[q.question]}`).join("; "));
  return (
    <div className="card" data-testid="clarify">
      <p className="muted">{r.intro} {r.why}</p>
      {r.questions.map((q: any) => (
        <div key={q.question}>
          <p className="title">{q.question}</p>
          <div className="chips">
            {q.options.map((o: string) => (
              <button key={o} className={`chip ${picked[q.question] === o ? "on" : ""}`}
                      onClick={() => setPicked({ ...picked, [q.question]: o })}>{o}</button>
            ))}
          </div>
        </div>
      ))}
      <button disabled={!ready} onClick={answer}>Run</button>
    </div>
  );
}

function Suggestions({ items }: { items?: any[] }) {
  const [state, setState] = useState<Record<string, string>>({});
  if (!items?.length) return null;
  return (
    <>
      {items.map((s) => (
        <div key={s.id} className="card remember" data-testid="remember">
          <p><b>Remember this?</b> {s.title}: {s.body}</p>
          {state[s.id] ? <p className="muted">{state[s.id]}</p> : (
            <div className="row">
              <button onClick={async () => setState({ ...state, [s.id]: (await call("POST", `/suggestions/${s.id}`, { accept: true })).message })}>Remember (only for me)</button>
              <button className="link" onClick={async () => setState({ ...state, [s.id]: (await call("POST", `/suggestions/${s.id}`, { accept: false })).message })}>No thanks</button>
            </div>
          )}
        </div>
      ))}
    </>
  );
}

function RequestFix({ turnId, done }: { turnId: string; done: () => void }) {
  const [text, setText] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  if (sent) return <p className="muted">{sent}</p>;
  return (
    <div className="row">
      <input aria-label="What should change" value={text} onChange={(e) => setText(e.target.value)}
             placeholder="Describe, in your own words, what should change" />
      <button onClick={async () => setSent((await call("POST", "/requests", { kind: "fix_report", text, turn_id: turnId })).message)}>Send</button>
      <button className="link" onClick={done}>Cancel</button>
    </div>
  );
}
