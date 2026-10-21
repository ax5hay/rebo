import { Eye, FileDown, FileText, RefreshCcw } from "lucide-react";
import { useState } from "react";
import { call, get, getText } from "../api";
import { useToast } from "../shell";
import { CodeEditor } from "../code";
import { Md } from "../md";

export default function AdminPage() {
  const toast = useToast();
  const [yaml, setYaml] = useState<string | null>(null);
  const [diff, setDiff] = useState<any | null>(null);
  const [preview, setPreview] = useState<any | null>(null);
  const [who, setWho] = useState("");
  const [q, setQ] = useState("");

  return (
    <>
      <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
        <div style={{ flex: 1, minWidth: 280 }}>
          <p className="lead">Admin</p>
          <p className="intro">Everything learned as one editable file, what another person's question would be given,
            and a re-check of saved knowledge after the database changed.</p>
        </div>
        <button className="btn" onClick={async () => { try { const r = await call("POST", "/admin/revalidate"); toast(r.message ?? "Saved knowledge re-checked."); } catch (e) { toast((e as Error).message); } }}><RefreshCcw />Re-check saved knowledge</button>
      </div>

      <div className="section-title"><h2>Everything learned, as a file</h2><p>Edit, preview the changes, then import.</p></div>
      <div className="panel" style={{ padding: 16 }}>
        {yaml === null ? (
          <div className="row"><button className="btn" onClick={async () => { try { setYaml(await getText("/knowledge/export")); } catch (e) { toast((e as Error).message); } }}><FileText />Open the file</button>
            <span className="small muted">Set <code>status: verified</code> to share or <code>status: retired</code> to withdraw; new items need no id.</span></div>
        ) : (
          <>
            <CodeEditor lang="yaml" label="Knowledge file" value={yaml} onChange={(v) => { setYaml(v); setDiff(null); }} />
            <div className="row" style={{ marginTop: 10 }}>
              <button className="btn" onClick={async () => { try { setDiff(await call("POST", "/knowledge/import", { yaml, dry_run: true })); } catch (e) { toast((e as Error).message); } }}><Eye />Preview changes</button>
              <button className="btn primary" disabled={!diff || diff.errors.length > 0} onClick={async () => { try { toast((await call("POST", "/knowledge/import", { yaml })).message); setDiff(null); } catch (e) { toast((e as Error).message); } }}>Import</button>
              <a className="btn ghost" download="knowledge.yaml" href={`data:text/yaml;charset=utf-8,${encodeURIComponent(yaml)}`}><FileDown />Download</a>
              {!diff && <span className="small muted">Import is possible after a preview.</span>}
            </div>
            {diff && (
              <ul className="list" style={{ marginTop: 12, borderTop: "1px solid var(--border)" }}>
                <li><Md className="sub">{diff.message}</Md><span /></li>
                {diff.changes.map((c: any, i: number) => (
                  <li key={i}><div><div className="title">{c.title}</div>
                    {Object.entries(c.fields ?? {}).map(([k, [a, b]]: any) => <div className="sub" key={k}>{k}: <s>{String(a ?? "")}</s> → {String(b ?? "")}</div>)}</div>
                    <span className={`pill ${c.action === "withdraw" ? "danger" : c.action === "share" ? "verified" : "yours"}`}>{c.action}</span></li>
                ))}
                {diff.errors.map((e: string) => <li key={e}><div className="sub" style={{ color: "var(--danger)" }}>{e}</div><span /></li>)}
              </ul>
            )}
          </>
        )}
      </div>

      <div className="section-title"><h2>See a question as another person</h2><p>What ReBo would be given; nothing is asked of the model.</p></div>
      <div className="panel" style={{ padding: 16 }}>
        <form className="row" onSubmit={async (e) => { e.preventDefault(); try { setPreview(await get(`/admin/preview?user=${encodeURIComponent(who)}&q=${encodeURIComponent(q)}`)); } catch (err) { toast((err as Error).message); } }}>
          <input className="input" style={{ maxWidth: 200 }} aria-label="Person" placeholder="Their name" value={who} onChange={(e) => setWho(e.target.value)} />
          <input className="input" style={{ maxWidth: 480 }} aria-label="Their question" placeholder="Their question" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn" type="submit" disabled={!who || !q}>Show</button>
        </form>
        {preview && <pre className="code" style={{ marginTop: 12 }}>{preview.context}</pre>}
      </div>
    </>
  );
}
