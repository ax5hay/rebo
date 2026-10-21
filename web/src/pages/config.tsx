import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { call, get, when } from "../api";
import { useToast } from "../shell";

export default function ConfigPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const cfg = useQuery({ queryKey: ["config"], queryFn: () => get<any>("/admin/config") });
  const [yaml, setYaml] = useState("");
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<any | null>(null);
  useEffect(() => { if (cfg.data) setYaml(cfg.data.yaml); }, [cfg.data]);
  const reload = () => { qc.invalidateQueries({ queryKey: ["config"] }); setCheck(null); };

  return (
    <>
      <p className="lead">Configuration</p>
      <p className="intro">About twenty values: which database, which models, limits and access. What the data means
        is never set here; ReBo learns it. Keys stay in the environment. Changes apply after a restart.</p>
      <div className="panel" style={{ padding: 16, marginTop: 16 }}>
        <div className="small muted" style={{ marginBottom: 8 }}>{cfg.data?.path}</div>
        <textarea className="textarea code" rows={20} aria-label="Configuration file" value={yaml} onChange={(e) => { setYaml(e.target.value); setCheck(null); }} />
        <input className="input" style={{ marginTop: 10 }} aria-label="Why are you changing it" placeholder="Why are you changing it? Kept in the history." value={note} onChange={(e) => setNote(e.target.value)} />
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn" onClick={async () => { try { setCheck(await call("POST", "/admin/config/preview", { yaml })); } catch (e) { toast((e as Error).message); } }}><ShieldCheck />Check it</button>
          <button className="btn primary" disabled={!check?.ok} onClick={async () => { try { toast((await call("PUT", "/admin/config", { yaml, note })).message); reload(); } catch (e) { toast((e as Error).message); } }}>Save</button>
          {!check && <span className="small muted">Save is possible after a successful check.</span>}
        </div>
        {check && (
          <div className={`callout ${check.ok ? "" : "warn"}`} style={{ margin: "12px 0 0", display: "block" }}>
            <b>{check.message}</b>
            {check.errors.map((e: string) => <div key={e} className="small" style={{ marginTop: 4 }}>{e}</div>)}
            {check.changes.map((c: any) => <div key={c.setting} className="small" style={{ marginTop: 2 }}>{c.setting}: {c.from} → {c.to}</div>)}
          </div>
        )}
      </div>
      <div className="section-title"><h2>Earlier versions</h2></div>
      <ul className="list panel">
        {(cfg.data?.history ?? []).length === 0 && <li className="empty">No changes made here yet.</li>}
        {(cfg.data?.history ?? []).map((e: any) => (
          <li key={e.id}>
            <div><div className="title">{e.note || "No reason given"}</div><div className="sub">{e.actor}, {when(e.at)}</div></div>
            <div className="acts"><button className="btn ghost" onClick={async () => { try { toast((await call("POST", `/admin/config/rollback/${e.id}`)).message); reload(); } catch (err) { toast((err as Error).message); } }}>Restore the version before this</button></div>
          </li>
        ))}
      </ul>
    </>
  );
}
