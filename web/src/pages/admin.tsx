// Admin tools as cards: the knowledge file (export, edit, preview, import), what another person's
// question would be given, and a re-check of saved knowledge after the database changed. One tool
// opens at a time, full width under the cards.
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Eye, FileDown, FileText, RefreshCcw, ScanSearch, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { call, get, getText, plural } from "../api";
import { CodeEditor } from "../code";
import { Md } from "../md";
import { useToast } from "../shell";
import { KINDS, PageHead } from "../ui";

type Tool = "file" | "preview" | "recheck" | null;

export default function AdminPage() {
  const toast = useToast();
  const [tool, setTool] = useState<Tool>(null);
  const review = useQuery({ queryKey: ["review"], queryFn: () => get<any[]>("/review") });
  const requests = useQuery({ queryKey: ["requests", "open"], queryFn: () => get<any[]>("/requests") });
  const TOOLS = [
    { id: "file" as const, icon: FileText, title: "Everything learned, as one file", text: "Export all knowledge as YAML, edit titles, rules and queries, preview what would change, then import." },
    { id: "preview" as const, icon: ScanSearch, title: "See a question as someone else", text: "What ReBo would be given for another person's question: their knowledge, defaults and likely tables. No model is asked." },
    { id: "recheck" as const, icon: RefreshCcw, title: "Re-check after database changes", text: "Saved reports and rules are checked against today's structure; anything broken is set aside until fixed." },
  ];
  return (
    <div className="page">
      <PageHead title="Admin" lede="Tools for keeping what ReBo learned correct and current."
        stats={[{ n: review.data?.length ?? "–", label: "Waiting to be shared" }, { n: requests.data?.length ?? "–", label: "Open requests" }]}
        actions={<Link className="btn" to="/review">Open review<ArrowRight /></Link>} />
      <div className="toolgrid">
        {TOOLS.map((t) => (
          <button key={t.id} className={`toolcard${tool === t.id ? " on" : ""}`} aria-expanded={tool === t.id} onClick={() => setTool(tool === t.id ? null : t.id)}>
            <span className="toolicon"><t.icon /></span>
            <b>{t.title}</b>
            <span className="muted">{t.text}</span>
            <span className="more">{tool === t.id ? "Close" : "Open"}<ArrowRight /></span>
          </button>
        ))}
      </div>
      {tool === "file" && <KnowledgeFile toast={toast} />}
      {tool === "preview" && <PreviewAs toast={toast} />}
      {tool === "recheck" && <Recheck toast={toast} />}
    </div>
  );
}

function KnowledgeFile({ toast }: { toast: (s: string) => void }) {
  const [yaml, setYaml] = useState<string | null>(null);
  const [diff, setDiff] = useState<any | null>(null);
  useEffect(() => { getText("/knowledge/export").then(setYaml, (e) => toast((e as Error).message)); }, []);  // eslint-disable-line react-hooks/exhaustive-deps
  if (yaml === null) return <div className="panel toolpanel"><p className="muted">Opening the file…</p></div>;
  return (
    <section className="panel toolpanel">
      <div className="toolbar">
        <h2>Knowledge file</h2>
        <span className="muted small">Set <code>status: verified</code> to share, <code>status: retired</code> to withdraw; new items need no id.</span>
        <span className="spacer" />
        <a className="btn ghost small" download="knowledge.yaml" href={`data:text/yaml;charset=utf-8,${encodeURIComponent(yaml)}`}><FileDown />Download</a>
        <button className="btn small" onClick={async () => { try { setDiff(await call("POST", "/knowledge/import", { yaml, dry_run: true })); } catch (e) { toast((e as Error).message); } }}><Eye />Preview changes</button>
        <button className="btn small primary" disabled={!diff || diff.errors.length > 0} onClick={async () => { try { toast((await call("POST", "/knowledge/import", { yaml })).message); setDiff(null); } catch (e) { toast((e as Error).message); } }}><Upload />Import</button>
      </div>
      <CodeEditor lang="yaml" label="Knowledge file" value={yaml} onChange={(v) => { setYaml(v); setDiff(null); }} />
      {!diff && <p className="hint">Import becomes possible after a preview shows what would change.</p>}
      {diff && (
        <div className={`result ${diff.errors.length ? "bad" : "ok"}`}>
          <Md className="resulthead">{diff.message}</Md>
          {diff.errors.map((e: string) => <p key={e} className="err">{e}</p>)}
          {diff.changes.length > 0 && (
            <ul className="changes">
              {diff.changes.map((c: any, i: number) => (
                <li key={i}>
                  <span className={`pill ${c.action === "withdraw" ? "danger" : c.action === "share" ? "verified" : "yours"}`}>{c.action}</span>
                  <b>{c.title}</b>
                  {Object.entries(c.fields ?? {}).map(([k, [a, b]]: any) => <span className="fieldchange" key={k}><span className="muted">{k}</span> <s>{String(a ?? "–")}</s> <ArrowRight size={13} /> {String(b ?? "–")}</span>)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function PreviewAs({ toast }: { toast: (s: string) => void }) {
  const [who, setWho] = useState("");
  const [q, setQ] = useState("");
  const [preview, setPreview] = useState<any | null>(null);
  return (
    <section className="panel toolpanel">
      <div className="toolbar"><h2>See a question as someone else</h2></div>
      <form className="sentence" onSubmit={async (e) => { e.preventDefault(); try { setPreview(await get(`/admin/preview?user=${encodeURIComponent(who)}&q=${encodeURIComponent(q)}`)); } catch (err) { toast((err as Error).message); } }}>
        <span>If</span>
        <input className="input" style={{ maxWidth: 180 }} aria-label="Person" placeholder="their name" value={who} onChange={(e) => setWho(e.target.value)} />
        <span>asked</span>
        <input className="input" style={{ flex: 1, minWidth: 220 }} aria-label="Their question" placeholder="their question" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn primary" type="submit" disabled={!who || !q}><Eye />Show</button>
      </form>
      {preview && (
        <div className="previewout">
          <h3>Knowledge they would get</h3>
          {preview.knowledge.length === 0 ? <p className="muted">None: ReBo would work from the database alone.</p> : (
            <ul className="rows">{preview.knowledge.map((i: any) => <li key={i.id ?? i.title}><span><b>{i.title}</b> <span className="muted">from {i.owner}</span></span><span className="pill">{KINDS[i.kind]?.label ?? i.kind}</span></li>)}</ul>
          )}
          <details className="query"><summary>Everything the model would read ({plural(preview.context.split("\n").length, "line", "lines")})</summary><pre className="code">{preview.context}</pre></details>
        </div>
      )}
    </section>
  );
}

function Recheck({ toast }: { toast: (s: string) => void }) {
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section className="panel toolpanel">
      <div className="toolbar"><h2>Re-check saved knowledge</h2></div>
      <p className="muted">Run this after the database changes (new or renamed tables and columns). The owners of anything that no longer runs are told, and it stops being used until fixed. Renamed columns often come back on their own.</p>
      <button className="btn primary" disabled={busy} onClick={async () => {
        setBusy(true);
        try { const r = await call("POST", "/admin/revalidate"); setResult(r.message ?? "Saved knowledge re-checked."); toast(r.message ?? "Saved knowledge re-checked."); }
        catch (e) { toast((e as Error).message); } finally { setBusy(false); }
      }}><RefreshCcw />{busy ? "Checking…" : "Re-check now"}</button>
      {result && <div className="result ok"><Md className="resulthead">{result}</Md></div>}
    </section>
  );
}
