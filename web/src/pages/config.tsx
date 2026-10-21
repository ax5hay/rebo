// Configuration (owners): the editor on the left, and on the right what a check found (every changed
// setting, from and to), the rules of the file, and every earlier version with a restore. Saving is
// possible only after a successful check of exactly what is in the editor.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CircleAlert, CircleCheck, History, KeyRound, Lock, RotateCcw, Save, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { call, get, when } from "../api";
import { Md } from "../md";
import { CodeEditor } from "../code";
import { useToast } from "../shell";
import { PageHead } from "../ui";

export default function ConfigPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const cfg = useQuery({ queryKey: ["config"], queryFn: () => get<any>("/admin/config") });
  const [yaml, setYaml] = useState("");
  const [note, setNote] = useState("");
  const [check, setCheck] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (cfg.data) setYaml(cfg.data.yaml); }, [cfg.data]);
  const reload = () => { qc.invalidateQueries({ queryKey: ["config"] }); setCheck(null); setNote(""); };
  const dirty = cfg.data && yaml !== cfg.data.yaml;
  const lines = yaml.split("\n").filter((l) => l.trim() && !l.trim().startsWith("#")).length;
  const history: any[] = cfg.data?.history ?? [];

  return (
    <div className="page wide">
      <PageHead title="Configuration"
        lede="Which database, which models, limits and access. What the data means is never set here: ReBo learns it from the database and from people."
        stats={[{ n: lines, label: "Lines set" }, { n: history.length, label: "Earlier versions" }, { n: dirty ? "Edited" : "Saved", label: "This file", tone: dirty ? "warn" : "ok" }]} />
      <div className="configgrid">
        <section className="panel toolpanel">
          <div className="toolbar">
            <span className="filepath"><Lock size={13} />{cfg.data?.path}</span>
            <span className="spacer" />
            <button className="btn small" disabled={busy} onClick={async () => { setBusy(true); try { setCheck(await call("POST", "/admin/config/preview", { yaml })); } catch (e) { toast((e as Error).message); } finally { setBusy(false); } }}><ShieldCheck />{busy ? "Checking…" : "Check it"}</button>
          </div>
          <CodeEditor lang="yaml" label="Configuration file" rows={22} value={yaml} onChange={(v) => { setYaml(v); setCheck(null); }} />
          <div className="savebar">
            <input className="input" aria-label="Why are you changing it" placeholder="Why are you changing it? Kept with this version." value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn primary" disabled={!check?.ok} title={check?.ok ? "" : "Check it first"} onClick={async () => { try { toast((await call("PUT", "/admin/config", { yaml, note })).message); reload(); } catch (e) { toast((e as Error).message); } }}><Save />Save</button>
          </div>
          <p className="hint">{check?.ok ? "Checked. Saving keeps the previous version, and changes apply after a restart." : "Save becomes possible after a successful check of exactly this text."}</p>
        </section>

        <aside className="rail">
          <section className={`card railcard ${check ? (check.ok ? "ok" : "bad") : ""}`}>
            <h2>{check ? (check.ok ? <CircleCheck /> : <CircleAlert />) : <ShieldCheck />}{check ? (check.ok ? "Ready to save" : "Not ready") : "Check before saving"}</h2>
            {!check && <p className="muted small">The check connects to the database, validates every model name and lists each setting that would change. Nothing is saved.</p>}
            {check && <Md className="small">{check.message}</Md>}
            {check?.errors?.map((e: string) => <p key={e} className="err small">{e}</p>)}
            {check?.changes?.length > 0 && (
              <ul className="changes">
                {check.changes.map((c: any) => (
                  <li key={c.setting}><b>{c.setting.replaceAll("_", " ")}</b><span className="fieldchange"><s>{String(c.from || "–")}</s><ArrowRight size={13} />{String(c.to || "–")}</span></li>
                ))}
              </ul>
            )}
          </section>
          <section className="card railcard">
            <h2><KeyRound />Rules of this file</h2>
            <ul className="ticks small">
              <li>No meaning goes here: no glossaries, no business rules. People teach those.</li>
              <li>Keys stay in the environment (<code>.env</code>), never in this file.</li>
              <li>About twenty values; each has a default that keeps today's behaviour.</li>
            </ul>
          </section>
          <section className="card railcard">
            <h2><History />Earlier versions</h2>
            {history.length === 0 ? <p className="muted small">No changes saved from here yet. Each save keeps the previous version.</p> : (
              <ol className="timeline">
                {history.map((e: any) => (
                  <li key={e.id}>
                    <span className="tdot" aria-hidden />
                    <div>
                      <div className="tline"><b>{e.note || "No reason given"}</b></div>
                      <div className="muted small">{e.actor}, {when(e.at)}</div>
                      <button className="btn small ghost" onClick={async () => { try { toast((await call("POST", `/admin/config/rollback/${e.id}`)).message); reload(); } catch (err) { toast((err as Error).message); } }}><RotateCcw />Restore the version before</button>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
