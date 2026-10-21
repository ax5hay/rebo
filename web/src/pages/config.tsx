import { useQuery, useQueryClient } from "@tanstack/react-query";
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
      <div className="pagehead">
        <h1>Configuration</h1>
        <p>About twenty values: which database, which models, limits and access. What the data means is
          never set here; ReBo learns it. Keys stay in the environment. Changes apply after a restart.</p>
      </div>
      <p className="small soft">{cfg.data?.path}</p>
      <textarea className="input" rows={24} aria-label="Configuration file" value={yaml} onChange={(e) => { setYaml(e.target.value); setCheck(null); }} />
      <input className="input" style={{ marginTop: 8 }} aria-label="Why are you changing it" placeholder="Why are you changing it? (kept in the history)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn" onClick={async () => { try { setCheck(await call("POST", "/admin/config/preview", { yaml })); } catch (e) { toast((e as Error).message); } }}>Check it</button>
        <button className="btn primary" disabled={!check?.ok} onClick={async () => { try { toast((await call("PUT", "/admin/config", { yaml, note })).message); reload(); } catch (e) { toast((e as Error).message); } }}>Save</button>
        <span className="small soft">Saving is possible after a successful check.</span>
      </div>
      {check && (
        <div className={`note ${check.ok ? "ok" : "bad"}`}>
          <p style={{ margin: 0, fontWeight: 700 }}>{check.message}</p>
          {check.errors.map((e: string) => <p key={e} style={{ margin: "4px 0" }}>{e}</p>)}
          {check.changes.map((c: any) => <p key={c.setting} className="small" style={{ margin: "2px 0" }}>{c.setting}: {c.from} → {c.to}</p>)}
        </div>
      )}
      <h2>Earlier versions</h2>
      <div className="ledger">
        {(cfg.data?.history ?? []).length === 0 && <p className="empty">No changes made here yet.</p>}
        {(cfg.data?.history ?? []).map((e: any) => (
          <div className="entry" key={e.id}>
            <div className="kind">{e.actor}<span>{when(e.at)}</span></div>
            <div className="body">{e.note || "No reason given."}</div>
            <div className="acts"><button className="btn quiet" onClick={async () => { try { toast((await call("POST", `/admin/config/rollback/${e.id}`)).message); reload(); } catch (err) { toast((err as Error).message); } }}>Go back to the version before this</button></div>
          </div>
        ))}
      </div>
    </>
  );
}
