// Health, accuracy and use of the bot. Traces and per-call detail live in Phoenix; this page shows what an
// admin needs to know at a glance and links there.
import * as Plot from "@observablehq/plot";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { get, plural, when } from "../api";

const pct = (frac?: string) => {
  if (!frac || !frac.includes("/")) return null;
  const [a, b] = frac.split("/").map(Number);
  return b ? a / b : null;
};

export default function InsightsPage() {
  const ins = useQuery({ queryKey: ["insights"], queryFn: () => get<any>("/insights") });
  const d = ins.data;
  const u = d?.usage;
  const weeks = u ? Object.entries(u.confirmation_by_week as Record<string, any>) : [];
  const reports = weeks.reduce((n, [, w]) => n + w.reports, 0);
  const confirmed = weeks.reduce((n, [, w]) => n + w.confirmed, 0);
  const cost = u ? Object.values(u.cost_per_day_usd as Record<string, number>).reduce((a, b) => a + b, 0) : 0;
  const failing = (d?.checks ?? []).filter((c: any) => c.state !== "ok").length;

  return (
    <>
      <div className="pagehead">
        <h1>Insights</h1>
        <p>Is ReBo working, is it right, and what does it cost? Each answer's full trace (every model call and
          query) is in Phoenix.</p>
        <div className="actions">
          {d?.phoenix && <a className="btn" href={d.phoenix} target="_blank" rel="noopener">Open traces in Phoenix</a>}
          <button className="btn quiet" onClick={() => ins.refetch()}>Check again</button>
        </div>
      </div>

      {d && (
        <div className="figures" aria-label="Last 90 days">
          <div><strong>{failing === 0 ? "Healthy" : `${failing} to look at`}</strong><span>{d.checks.length} checks just now</span></div>
          <div><strong>{u.turns}</strong><span>questions in 90 days</span></div>
          <div><strong>{reports ? `${Math.round((confirmed / reports) * 100)}%` : "–"}</strong><span>reports confirmed by the asker</span></div>
          <div><strong>{latestAccuracy(d.accuracy)}</strong><span>latest measured accuracy</span></div>
          <div><strong>${cost.toFixed(2)}</strong><span>model cost at list prices</span></div>
        </div>
      )}

      <h2>Health</h2>
      <div className="board">
        {(d?.checks ?? []).map((c: any) => (
          <div className={`check ${c.state}`} key={c.name}>
            <span className="dot" aria-label={c.state} />
            <b>{c.name}</b>
            <span className="detail">{c.detail}</span>
            <span className="ms">{c.ms} ms</span>
          </div>
        ))}
        {ins.isLoading && <p className="empty">Running the checks…</p>}
        {ins.isError && <p className="empty">{(ins.error as Error).message}</p>}
      </div>

      <h2>Accuracy over time</h2>
      <p className="soft small">Share of gold answers matched (content, not presentation) and conversations solved, per measured run.</p>
      <Accuracy runs={d?.accuracy ?? []} />

      <h2>Confirmed by the people who asked</h2>
      <Weekly weeks={weeks} />

      <h2>Where answers came from</h2>
      <div className="ledger">
        {u && Object.entries(u.provenance).map(([k, n]: any) => (
          <div className="entry" key={k}><div className="kind">{k}</div><div className="title">{plural(n, "report", "reports")}</div><div /></div>
        ))}
      </div>

      <h2>Most asked</h2>
      <div className="ledger">
        {(u?.top_questions ?? []).map((t: any) => <div className="entry" key={t.question}><div className="kind">{plural(t.count, "time", "times")}</div><div className="body">{t.question}</div><div /></div>)}
      </div>

      <h2>Most often reported wrong</h2>
      <div className="ledger">
        {(u?.most_reported_wrong ?? []).length === 0 && <p className="empty">Nothing has been reported wrong.</p>}
        {(u?.most_reported_wrong ?? []).map((w: any) => <div className="entry" key={w.id}><div className="kind">{plural(w.rejections, "time", "times")}</div><div><div className="title">{w.title}</div><div className="meta">{w.kind}, {w.status}</div></div><div /></div>)}
      </div>

      <h2>Measured runs</h2>
      <div className="ledger">
        {(d?.accuracy ?? []).slice().reverse().map((r: any) => (
          <div className="entry" key={r.id}>
            <div className="kind">{r.kind}<span>{when(r.at)}</span></div>
            <div><div className="title">{r.model}</div><div className="meta">{r.cases}, {summaryLine(r)}</div></div>
            <div />
          </div>
        ))}
      </div>
    </>
  );
}

function latestAccuracy(runs: any[]) {
  const q = runs.filter((r) => r.kind === "questions" && pct(r.summary.execution_match) !== null);
  const last = q[q.length - 1];
  return last ? `${Math.round(pct(last.summary.execution_match)! * 100)}%` : "–";
}

function summaryLine(r: any) {
  const s = r.summary;
  if (r.kind === "conversations") return `${s.solved} of ${s.conversations} solved, ${s.mean_turns_to_first_correct ?? "–"} turns to the right answer`;
  return [s.execution_match && `${s.execution_match} matched`, plural(s.reports, "report", "reports"),
          plural(s.clarify, "question back", "questions back"), plural(s.errors, "error", "errors"),
          s.total_cost_usd != null && `$${s.total_cost_usd}`].filter(Boolean).join(", ");
}

function usePlot(make: () => (SVGSVGElement | HTMLElement) | null, deps: unknown[]) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = make();
    if (!el || !ref.current) return;
    ref.current.replaceChildren(el);
    return () => el.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return ref;
}

function Accuracy({ runs }: { runs: any[] }) {
  // In the order they were measured; labelled by date (several runs can share one).
  const data = runs.map((r, i) => ({
    run: `${i + 1}. ${when(r.at)}`,
    value: r.kind === "conversations" ? r.summary.solved / Math.max(r.summary.conversations, 1) : pct(r.summary.execution_match),
    series: `${r.kind === "conversations" ? "conversations" : r.cases.split("/").pop()}, ${String(r.model).split(":").pop()}`,
  })).filter((p) => p.value !== null);
  const ref = usePlot(() => data.length ? Plot.plot({
    width: 960, height: 280, marginLeft: 48, style: { background: "transparent", fontSize: "13px" },
    y: { domain: [0, 1], tickFormat: "%", label: null, grid: true },
    x: { label: null, domain: data.map((d) => d.run), padding: 0.5 }, color: { legend: true },
    marks: [Plot.ruleY([0]), Plot.dot(data, { x: "run", y: "value", stroke: "series", r: 6, strokeWidth: 3, tip: true }),
            Plot.lineY(data, { x: "run", y: "value", stroke: "series", strokeWidth: 1.5 })],
  }) : null, [JSON.stringify(data)]);
  return data.length ? <div className="plot" ref={ref} /> : <p className="empty">No measured runs yet. Run tools/eval_run.py with a key; runs are recorded here.</p>;
}

function Weekly({ weeks }: { weeks: [string, any][] }) {
  const data = weeks.flatMap(([w, v]) => [
    { week: w, n: v.confirmed, what: "confirmed" }, { week: w, n: v.rejected, what: "reported wrong" },
    { week: w, n: v.reports - v.confirmed - v.rejected, what: "no feedback" },
  ]);
  const ref = usePlot(() => data.length ? Plot.plot({
    width: 960, height: 220, marginLeft: 40, style: { background: "transparent", fontSize: "13px" },
    x: { label: null }, y: { label: "reports", grid: true, tickFormat: "d", ticks: Math.max(...data.map((d) => d.n), 1) }, color: { legend: true, domain: ["confirmed", "reported wrong", "no feedback"], range: ["#2f7d4f", "#c2410c", "#b8c2ba"] },
    marks: [Plot.barY(data, { x: "week", y: "n", fill: "what", tip: true }), Plot.ruleY([0])],
  }) : null, [JSON.stringify(data)]);
  return data.length ? <div className="plot" ref={ref} /> : <p className="empty">No reports yet in the last 90 days.</p>;
}
