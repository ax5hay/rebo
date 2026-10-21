import { useState } from "react";
import { call, get, getText } from "../api";
import { useToast } from "../shell";

export default function AdminPage() {
  const toast = useToast();
  const [yaml, setYaml] = useState<string | null>(null);
  const [diff, setDiff] = useState<any | null>(null);
  const [preview, setPreview] = useState<any | null>(null);
  const [who, setWho] = useState("");
  const [q, setQ] = useState("");

  return (
    <>
      <div className="pagehead">
        <h1>Admin</h1>
        <p>Everything learned as one editable file, a check of what another person's question would be
          given, and a re-check of saved knowledge after the database changed.</p>
        <div className="actions">
          <button className="btn" onClick={async () => { try { const r = await call("POST", "/admin/revalidate"); toast(r.message ?? `Checked ${r.checked ?? ""} items.`); } catch (e) { toast((e as Error).message); } }}>Re-check saved knowledge</button>
        </div>
      </div>

      <h2>Everything learned, as a file</h2>
      <p className="soft">Edit titles, questions, meanings and queries; set <code>status: verified</code> to share or
        <code> status: retired</code> to withdraw. Preview the changes before importing.</p>
      {yaml === null ? (
        <button className="btn" onClick={async () => { try { setYaml(await getText("/knowledge/export")); } catch (e) { toast((e as Error).message); } }}>Open the file</button>
      ) : (
        <>
          <textarea className="input" rows={18} aria-label="Knowledge file" value={yaml} onChange={(e) => { setYaml(e.target.value); setDiff(null); }} />
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn" onClick={async () => { try { setDiff(await call("POST", "/knowledge/import", { yaml, dry_run: true })); } catch (e) { toast((e as Error).message); } }}>Preview changes</button>
            <button className="btn primary" disabled={!diff || diff.errors.length > 0} onClick={async () => { try { toast((await call("POST", "/knowledge/import", { yaml })).message); setDiff(null); } catch (e) { toast((e as Error).message); } }}>Import</button>
            <a className="btn quiet" download="knowledge.yaml" href={`data:text/yaml;charset=utf-8,${encodeURIComponent(yaml)}`}>Download</a>
          </div>
          {diff && (
            <div className="ledger" style={{ marginTop: 12 }}>
              <p className="soft">{diff.message}</p>
              {diff.changes.map((c: any, i: number) => (
                <div className="entry" key={i}>
                  <div className="kind">{c.action}</div>
                  <div><div className="title">{c.title}</div>
                    {Object.entries(c.fields ?? {}).map(([k, [a, b]]: any) => <div className="body" key={k}>{k}: <s>{String(a ?? "")}</s> → {String(b ?? "")}</div>)}
                  </div><div />
                </div>
              ))}
              {diff.errors.map((e: string) => <div className="note bad" key={e}>{e}</div>)}
            </div>
          )}
        </>
      )}

      <h2>See a question as another person</h2>
      <p className="soft">What ReBo would be given for this person's question: their own and shared knowledge,
        defaults, likely tables and stored values. Nothing is asked of the model.</p>
      <form className="row" onSubmit={async (e) => { e.preventDefault(); try { setPreview(await get(`/admin/preview?user=${encodeURIComponent(who)}&q=${encodeURIComponent(q)}`)); } catch (err) { toast((err as Error).message); } }}>
        <input className="input" style={{ maxWidth: 200 }} aria-label="Person" placeholder="their name" value={who} onChange={(e) => setWho(e.target.value)} />
        <input className="input" style={{ maxWidth: 480 }} aria-label="Their question" placeholder="their question" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn" type="submit" disabled={!who || !q}>Show</button>
      </form>
      {preview && <pre className="sql">{preview.context}</pre>}
    </>
  );
}
