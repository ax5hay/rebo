import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowRight, ArrowUp, Check, CircleHelp, History, Pin, Sparkle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { askStream, call, get, when, type Step } from "../api";
import { Question, TurnView, type Turn } from "../answer";
import { DemoNotice, useDemo } from "../demo";
import { Glass } from "../glass";
import { useMe } from "../shell";

const newThread = () => `conv_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;

export default function AskPage() {
  const me = useMe();
  const { conversationId } = useParams();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [thread, setThread] = useState(conversationId ?? newThread());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [trail, setTrail] = useState<string[]>([]);
  const [away, setAway] = useState(false);  // scrolled up, away from the newest answer
  const [fixing, setFixing] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  const history = useQuery({ queryKey: ["conversation", conversationId], enabled: !!conversationId,
                             queryFn: () => get<any[]>(`/conversations/${conversationId}`) });
  useEffect(() => {
    if (conversationId) setThread(conversationId);
    if (history.data) setTurns(history.data.map((r) => ({ key: r.turn_id, question: r.question, r })));
    if (!conversationId) { setTurns([]); setThread(newThread()); }
  }, [conversationId, history.data]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length, busy]);
  useEffect(() => {
    const el = end.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setAway(!e.isIntersecting), { rootMargin: "0px 0px -120px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [turns.length > 0]);
  useEffect(() => {  // a question typed in the command palette
    const q = search.get("q");
    if (q) { setSearch({}, { replace: true }); ask(q); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);
  useEffect(() => {  // the composer grows with the question
    if (box.current) { box.current.style.height = "auto"; box.current.style.height = `${Math.min(box.current.scrollHeight, 160)}px`; }
  }, [text]);

  async function ask(question: string) {
    question = question.trim();
    if (!question || busy) return;
    let sent = question;
    if (fixing) {
      await call("POST", `/turns/${fixing}/feedback`, { verdict: "wrong", note: question }).catch(() => {});
      sent = `Correction to the previous report: ${question}`;
      setFixing(null);
    }
    setText("");
    setTurns((t) => [...t, { key: `pending-${Date.now()}`, question, r: { kind: "pending" } }]);
    setBusy("Reading your question…");
    setTrail(["Reading your question"]);
    try {
      const r = await askStream(sent, thread, (s: Step) => {
        const say = String(s.say ?? "Working…").replace(/…$/, "");
        setBusy(say);
        setTrail((t) => (t[t.length - 1] === say ? t : [...t, say].slice(-6)));
      });
      setTurns((t) => [...t.filter((x) => x.r.kind !== "pending"), { key: r.turn_id, question, r }]);
      if (!conversationId) navigate(`/c/${thread}`, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      setTurns((t) => [...t.filter((x) => x.r.kind !== "pending"), { key: crypto.randomUUID(), question, r: { kind: "error", message: (e as Error).message } }]);
    } finally {
      setBusy(null);
    }
  }

  const add = (question: string, r: any) => setTurns((t) => [...t, { key: r.turn_id, question, r }]);
  const empty = turns.length === 0 && !busy && !conversationId;

  return (
    <>
      {empty ? <Start ask={ask} name={me?.id ?? ""} /> : (
        <div className="thread">
          {turns.map((t, i) => t.r.kind === "pending" ? (
            <div key={t.key} className="turn">
              <Question n={i + 1} text={t.question} />
              <Trail steps={trail} />
            </div>
          ) : <TurnView key={t.key} t={t} n={i + 1} ask={ask} onTurn={add} onFix={(id) => { setFixing(id); box.current?.focus(); }} />)}
          <div ref={end} />
        </div>
      )}
      <div className="composer">
        {away && turns.length > 1 && (
          <Glass as="button" className="jump" strength={14} onClick={() => end.current?.scrollIntoView({ behavior: "smooth", block: "end" })}>
            <ArrowDown />Latest answer
          </Glass>
        )}
        <Glass className="composerglass" strength={20}>
          {fixing && <div className="hint">Say what should be different, for example “only count the active ones”. ReBo redoes the report.</div>}
          <form onSubmit={(e) => { e.preventDefault(); ask(text); }}>
            <textarea ref={box} rows={1} aria-label="Your question" value={text} autoFocus
                      placeholder={fixing ? "What should change?" : "Ask for a report in plain words"}
                      onChange={(e) => setText(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(text); } }} />
            <button className="send" type="submit" disabled={!!busy || !text.trim()} aria-label={fixing ? "Fix it" : "Ask"} title={fixing ? "Fix it" : "Ask (Enter)"}>
              <ArrowUp />
            </button>
          </form>
          <p className="notice" role="note"><Sparkle />ReBo is an AI. The rows are real data, but it can misread a question,
            so each answer says how it read yours, and your corrections teach it. <Link to="/help#safety">How to check</Link></p>
        </Glass>
      </div>
    </>
  );
}

// What ReBo is doing, as it happens: finished steps ticked, the current one live, with a running clock.
function Trail({ steps }: { steps: string[] }) {
  const [s, setS] = useState(0);
  useEffect(() => { const t = setInterval(() => setS((x) => x + 1), 1000); return () => clearInterval(t); }, []);
  return (
    <div className="trail" role="status" aria-live="polite">
      <ol>{steps.map((x, i) => (
        <li key={i} className={i === steps.length - 1 ? "now" : "done"}>
          {i === steps.length - 1 ? <span className="spinner" aria-hidden /> : <Check aria-hidden />}{x}
        </li>
      ))}</ol>
      <span className="clock">{s}s</span>
    </div>
  );
}

function Start({ ask, name }: { ask: (q: string) => void; name: string }) {
  const starters = useQuery({ queryKey: ["starter"], queryFn: () => get<string[]>("/starter") });
  const recent = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations") });
  const k = useQuery({ queryKey: ["knowledge"], queryFn: () => get<any>("/knowledge") });
  const pinned = (k.data?.mine ?? []).filter((i: any) => i.pinned && i.status !== "retired");
  const navigate = useNavigate();
  const demo = useDemo();
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return (
    <div className="start">
      <section className="hello">
        <h1>{greeting}, {name}.</h1>
        <p>Ask for any report in your own words. You get the rows, how your question was read, and where the
          answer came from. Each answer you confirm or correct makes the next one better.</p>
      </section>
      {demo && <DemoNotice demo={demo} />}
      {(starters.data?.length ?? 0) > 0 && (
        <section className="block">
          <h2>Try a known report</h2>
          <div className="chips">{starters.data!.slice(0, 8).map((s) => <Glass as="button" key={s} className="chip big" strength={12} onClick={() => ask(s)}><Sparkle />{s}</Glass>)}</div>
        </section>
      )}
      <div className="startgrid">
        {pinned.length > 0 && (
          <section className="card">
            <h2><Pin />Pinned</h2>
            <ul className="rows">{pinned.slice(0, 6).map((i: any) => <li key={i.id}><button className="linkrow" onClick={() => ask(i.question || i.title)}><span>{i.title}</span><ArrowRight /></button></li>)}</ul>
          </section>
        )}
        {(recent.data?.length ?? 0) > 0 && (
          <section className="card">
            <h2><History />Pick up where you left off</h2>
            <ul className="rows">
              {recent.data!.slice(0, 6).map((c) => (
                <li key={c.id}><button className="linkrow" onClick={() => navigate(`/c/${c.id}`)}><span>{c.title}</span><span className="w">{when(c.updated_at)}</span></button></li>
              ))}
            </ul>
          </section>
        )}
        <section className="card quiet">
          <h2><CircleHelp />New here?</h2>
          <p className="muted">Two minutes on how to ask, check and teach.</p>
          <Link className="more" to="/help">Read how ReBo works<ArrowRight /></Link>
        </section>
      </div>
    </div>
  );
}
