import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { askStream, call, get, when, type Step } from "../api";
import { TurnView, type Turn } from "../answer";
import { useMe } from "../shell";

const newThread = () => `conv_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;

export default function AskPage() {
  const me = useMe();
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [thread, setThread] = useState(conversationId ?? newThread());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [fixing, setFixing] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  const history = useQuery({ queryKey: ["conversation", conversationId], enabled: !!conversationId,
                             queryFn: () => get<any[]>(`/conversations/${conversationId}`) });
  useEffect(() => {
    if (conversationId) setThread(conversationId);
    if (history.data) setTurns(history.data.map((r) => ({ key: r.turn_id, question: r.question, r })));
    if (!conversationId) { setTurns([]); setThread(newThread()); }
  }, [conversationId, history.data]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length, busy]);

  async function ask(question: string) {
    question = question.trim();
    if (!question || busy) return;
    let sent = question;
    if (fixing) {
      await fetchFeedback(fixing, question);
      sent = `Correction to the previous report: ${question}`;
      setFixing(null);
    }
    setText("");
    setBusy("Reading your question…");
    try {
      const r = await askStream(sent, thread, (s: Step) => setBusy(String(s.say ?? "Working…")));
      setTurns((t) => [...t, { key: r.turn_id, question, r }]);
      if (!conversationId) navigate(`/c/${thread}`, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      setTurns((t) => [...t, { key: crypto.randomUUID(), question, r: { kind: "error", message: (e as Error).message } }]);
    } finally {
      setBusy(null);
    }
  }

  const add = (question: string, r: any) => setTurns((t) => [...t, { key: r.turn_id, question, r }]);

  return (
    <>
      {turns.length === 0 && !busy && !conversationId ? <Start ask={ask} name={me?.id ?? ""} /> : (
        <div className="historybar">
          <button className="btn quiet" onClick={() => navigate("/")}>New conversation</button>
          <span className="small soft">Everything in this conversation is remembered for follow-up questions.</span>
        </div>
      )}
      {turns.map((t) => <TurnView key={t.key} t={t} ask={ask} onTurn={add} onFix={(id) => setFixing(id)} />)}
      {busy && <div className="working" role="status"><span className="tick" aria-hidden />{busy}</div>}
      <div ref={end} />
      <div className="composer">
        {fixing && <div className="hint">Say what should be different, for example “only count the active ones”. ReBo will redo the report.</div>}
        <form onSubmit={(e) => { e.preventDefault(); ask(text); }}>
          <input aria-label="Your question" value={text} onChange={(e) => setText(e.target.value)} autoFocus
                 placeholder={fixing ? "What should change?" : "Ask for a report in plain words"} />
          <button className="btn primary" type="submit" disabled={!!busy}>{fixing ? "Fix it" : "Ask"}</button>
        </form>
      </div>
    </>
  );
}

async function fetchFeedback(turnId: string, note: string) {
  await call("POST", `/turns/${turnId}/feedback`, { verdict: "wrong", note }).catch(() => {});
}

function Start({ ask, name }: { ask: (q: string) => void; name: string }) {
  const starters = useQuery({ queryKey: ["starter"], queryFn: () => get<string[]>("/starter") });
  const recent = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations") });
  const navigate = useNavigate();
  return (
    <section className="starters">
      <h1>What do you need to know, {name}?</h1>
      <p>Ask in your own words. You get the rows, how your question was read, and where the answer came
        from. Say whether it is right and ReBo remembers it, for you first.</p>
      {(starters.data?.length ?? 0) > 0 && (
        <>
          <h2>Start from a known report</h2>
          <div className="row">{starters.data!.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}</div>
        </>
      )}
      {(recent.data?.length ?? 0) > 0 && (
        <>
          <h2>Pick up where you left off</h2>
          <div className="history">
            {recent.data!.slice(0, 8).map((c) => (
              <button key={c.id} onClick={() => navigate(`/c/${c.id}`)}>{c.title}<span>{c.turns} {c.turns === 1 ? "answer" : "answers"}, last on {when(c.updated_at)}</span></button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
