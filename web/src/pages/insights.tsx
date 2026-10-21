// Health, accuracy and use of the bot. Per-answer detail (every model call and query) lives in Phoenix;
// this page shows what an admin needs at a glance and links there.
import * as Plot from "@observablehq/plot";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, RefreshCcw } from "lucide-react";
import { useEffect, useRef } from "react";
import { get, plural, when } from "../api";
import { Md } from "../md";

const pct = (frac?: string) => {
  if (!frac || !frac.includes("/")) return null;
  const [a, b] = frac.split("/").map(Number);
  return b ? a / b : null;
};
const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export default function InsightsPage() {
  const ins = useQuery({ queryKey: ["insights"], queryFn: () => get<any>("/insights") });
  const d = ins.data;
  const u = d?.usage;
  const weeks: [string, any][] = u ? Object.entries(u.confirmation_by_week) : [];
  const reports = weeks.reduce((n, [, w]) => n + w.reports, 0);
  const confirmed = weeks.reduce((n, [, w]) => n + w.confirmed, 0);
  const cost = u ? Object.values(u.cost_per_day_usd as Record<string, number>).reduce((a, b) => a + b, 0) : 0;
  const attention = (d?.checks ?? []).filter((c: any) => c.state !== "ok");

  return (
    <>
      <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
        <div style={{ flex: 1, minWidth: 280 }}>
          <p className="lead">Is ReBo working, is it right, what does it cost?</p>
          <p className="intro">Live checks, measured accuracy and use over the last 90 days. Every answer's full trace is in Phoenix.</p>
        </div>
        <div className="row">
          <button className="btn ghost" onClick={() => ins.refetch()}><RefreshCcw />Check again</button>
          {d?.phoenix && <a className="btn" href={d.phoenix} target="_blank" rel="noopener"><ExternalLink />Traces in Phoenix</a>}
        </div>
      </div>

      {d && (
        <div className="panel kpis" style={{ marginTop: 16 }}>
          <div><div className={`value ${attention.some((c: any) => c.state === "fail") ? "bad" : attention.length ? "warn" : "ok"}`}>{attention.length ? `${attention.length} to look at` : "All healthy"}</div><div className="label">{d.checks.length} checks just now</div></div>
          <div><div className="value">{latestAccuracy(d.accuracy)}</div><div className="label">Latest measured accuracy</div></div>
          <div><div className="value">{reports ? `${Math.round((confirmed / reports) * 100)}%` : "–"}</div><div className="label">Answers confirmed by the asker</div></div>
          <div><div className="value">{u.turns}</div><div className="label">Questions asked</div></div>
          <div><div className="value">${cost.toFixed(2)}</div><div className="label">Model cost at list prices</div></div>
        </div>
      )}

      <div className="section-title"><h2>Health</h2>{ins.isFetching && <p>checking…</p>}</div>
      <ul className="list panel checks">
        {(d?.checks ?? []).map((c: any) => (
          <li key={c.name} className={c.state}>
            <span className={`state ${c.state}`} aria-label={c.state} />
            <span className="title">{c.name}</span>
            <span className="sub" style={{ margin: 0 }}><Md inline>{c.detail}</Md></span>
            <span className="ms">{c.ms} ms</span>
          </li>
        ))}
        {ins.isError && <li className="empty">{(ins.error as Error).message}</li>}
      </ul>

      <div className="section-title"><h2>Accuracy over time</h2><p>Gold answers matched by content, and conversations solved, per measured run.</p></div>
      <div className="panel"><Accuracy runs={d?.accuracy ?? []} /></div>

      <div className="section-title"><h2>Feedback from the people who asked</h2></div>
      <div className="panel"><Weekly weeks={weeks} /></div>

      <div className="section-title"><h2>Where answers came from</h2></div>
      <ul className="list panel">
        {u && Object.entries(u.provenance).map(([k, n]: any) => <li key={k}><span className="title">{LABEL[k] ?? k}</span><span className="muted">{plural(n, "report", "reports")}</span></li>)}
        {u && Object.keys(u.provenance).length === 0 && <li className="empty">No reports yet.</li>}
      </ul>

      <div className="section-title"><h2>Most asked</h2></div>
      <ul className="list panel">
        {(u?.top_questions ?? []).map((t: any) => <li key={t.question}><span>{t.question}</span><span className="muted">{plural(t.count, "time", "times")}</span></li>)}
        {(u?.top_questions ?? []).length === 0 && <li className="empty">No questions yet.</li>}
      </ul>

      <div className="section-title"><h2>Most often reported wrong</h2></div>
      <ul className="list panel">
        {(u?.most_reported_wrong ?? []).length === 0 && <li className="empty">Nothing has been reported wrong.</li>}
        {(u?.most_reported_wrong ?? []).map((w: any) => <li key={w.id}><div><div className="title">{w.title}</div><div className="sub">{w.kind}, {w.status}</div></div><span className="pill danger">{plural(w.rejections, "time", "times")}</span></li>)}
      </ul>

      <div className="section-title"><h2>Measured runs</h2></div>
      <ul className="list panel">
        {(d?.accuracy ?? []).length === 0 && <li className="empty">No measured runs yet. Runs of tools/eval_run.py are recorded here.</li>}
        {(d?.accuracy ?? []).slice().reverse().map((r: any) => (
          <li key={r.id}>
            <div><div className="title">{String(r.model).split(":").pop()}</div><div className="sub">{r.cases.split("/").pop()}, {summaryLine(r)}</div></div>
            <span className="small muted">{when(r.at)}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

const LABEL: Record<string, string> = { verified: "Verified reports", yours: "People's own reports", adapted: "Built from saved knowledge", new: "New answers" };

function latestAccuracy(runs: any[]) {
  const q = runs.filter((r) => r.kind === "questions" && pct(r.summary.execution_match) !== null);
  const last = q[q.length - 1];
  return last ? `${Math.round(pct(last.summary.execution_match)! * 100)}%` : "–";
}

function summaryLine(r: any) {
  const s = r.summary;
  if (r.kind === "conversations") return `${s.solved} of ${s.conversations} conversations solved`;
  return [s.execution_match && `${s.execution_match} matched`, plural(s.reports, "report", "reports"),
          plural(s.errors, "error", "errors"), s.total_cost_usd != null && `$${s.total_cost_usd}`].filter(Boolean).join(", ");
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
  // In the order they were measured ("Run 1" … ), the date in the tooltip; one series per model.
  const data = runs.map((r, i) => ({
    run: `Run ${i + 1}`, when: when(r.at), cases: r.cases.split("/").slice(-2).join("/"),
    value: r.kind === "conversations" ? r.summary.solved / Math.max(r.summary.conversations, 1) : pct(r.summary.execution_match),
    series: `${String(r.model).split(":").pop()?.split("/").pop()}${r.kind === "conversations" ? " (conversations)" : ""}`,
  })).filter((p) => p.value !== null);
  const ref = usePlot(() => data.length ? Plot.plot({
    width: 1040, height: 260, marginLeft: 44, marginBottom: 36, style: { background: "transparent", fontSize: "12px", color: css("--text-2") },
    y: { domain: [0, 1], tickFormat: "%", label: null, grid: true },
    x: { label: null, domain: data.map((d) => d.run), padding: 0.5 }, color: { legend: true },
    marks: [Plot.ruleY([0], { stroke: css("--border-strong") }),
            Plot.lineY(data, { x: "run", y: "value", stroke: "series", strokeWidth: 1.5 }),
            Plot.dot(data, { x: "run", y: "value", fill: "series", r: 5, tip: true, channels: { when: "when", cases: "cases" } })],
  }) : null, [JSON.stringify(data)]);
  return data.length ? <div className="chart" ref={ref} /> : <div className="empty">No measured runs yet.</div>;
}

function Weekly({ weeks }: { weeks: [string, any][] }) {
  const data = weeks.flatMap(([w, v]) => [
    { week: w, n: v.confirmed, what: "confirmed" }, { week: w, n: v.rejected, what: "reported wrong" },
    { week: w, n: v.reports - v.confirmed - v.rejected, what: "no feedback" },
  ]);
  const ref = usePlot(() => data.length ? Plot.plot({
    width: 1040, height: 220, marginLeft: 40, style: { background: "transparent", fontSize: "12px", color: css("--text-2") },
    x: { label: null }, y: { label: "answers", grid: true, tickFormat: "d", ticks: Math.max(...data.map((d) => d.n), 1) },
    color: { legend: true, domain: ["confirmed", "reported wrong", "no feedback"], range: [css("--accent"), css("--danger"), css("--border-strong")] },
    marks: [Plot.barY(data, { x: "week", y: "n", fill: "what", tip: true, inset: 6 }), Plot.ruleY([0], { stroke: css("--border-strong") })],
  }) : null, [JSON.stringify(data)]);
  return data.length ? <div className="chart" ref={ref} /> : <div className="empty">No answers yet in the last 90 days.</div>;
}
