import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Button } from "react-aria-components";
import { call, get, when } from "../api";
import { Sheet } from "../answer";
import { useMe, useToast } from "../shell";
import { Md } from "../md";
import { CodeEditor, SqlCode } from "../code";

const KIND: Record<string, string> = { example: "Saved report", term: "Meaning of a word", note: "Rule or fact", join: "How tables connect" };

export default function KnowledgePage() {
  const me = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const k = useQuery({ queryKey: ["knowledge"], queryFn: () => get<any>("/knowledge") });
  const defaults = useQuery({ queryKey: ["defaults"], queryFn: () => get<any[]>("/defaults") });
  const requests = useQuery({ queryKey: ["requests", "mine"], queryFn: () => get<any[]>("/requests?status=") });
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: () => get<any[]>("/schedules") });
  const [editing, setEditing] = useState<any | null>(null);
  const [adding, setAdding] = useState(false);
  const [history, setHistory] = useState<any | null>(null);
  const refresh = () => ["knowledge", "defaults", "schedules"].forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
  const act = async (fn: () => Promise<any>) => { try { const r = await fn(); if (r?.message) toast(r.message); refresh(); } catch (e) { toast((e as Error).message); } };
  const mine = k.data?.mine ?? [];
  const shared = k.data?.shared ?? [];

  return (
    <>
      <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
        <div style={{ flex: 1, minWidth: 280 }}>
          <h1 className="lead">What you taught ReBo</h1>
          <p className="intro">It shapes answers for you only, until it is shared with everyone. Nothing is deleted:
            every change has a history and can be undone.</p>
        </div>
        <button className="btn primary" onClick={() => setAdding(true)}><Plus />Teach something new</button>
      </div>
      {k.data?.notice && <div className="callout warn" style={{ margin: "12px 0 0" }}>{k.data.notice}</div>}

      <Lookup />

      <div className="section-title" id="defaults"><h2>My defaults</h2><p>Applied to every question unless it says otherwise.</p></div>
      <Defaults rows={defaults.data ?? []} onSaved={refresh} />

      <div className="section-title" id="saved"><h2>Saved knowledge</h2><p>{mine.length || "None yet"}</p></div>
      <ul className="list panel">
        {mine.length === 0 && <li className="empty">Confirm a report with “Yes, this is right”, accept a “Remember this?” note, or teach something new.</li>}
        {mine.map((i: any) => (
          <li key={i.id}>
            <div>
              <div className="row" style={{ gap: 6 }}>
                <span className="pill">{KIND[i.kind]}</span>
                <span className={`pill ${i.status === "verified" ? "verified" : i.status === "stale" ? "warn" : ""}`}>{i.label}</span>
                {i.pinned ? <span className="pill yours">Pinned</span> : null}
              </div>
              <div className="title" style={{ marginTop: 6 }}>{i.title}</div>
              {i.question && <div className="sub">Asked as “{i.question}”</div>}
              {i.body && <Md className="sub">{i.body}</Md>}
              {i.sql && <details className="query"><summary>Query</summary><SqlCode sql={i.sql} /></details>}
              <div className="sub small">Confirmed {i.confirmations}×, used {i.uses}×, reported wrong {i.rejections}×</div>
            </div>
            <div className="acts">
              <button className="btn ghost" onClick={() => setEditing(i)}>Edit</button>
              {i.status !== "verified" && i.status !== "retired" && <button className="btn ghost" onClick={() => act(() => call("POST", `/knowledge/${i.id}/share`))}>Share</button>}
              {i.pinned ? <button className="btn ghost" onClick={() => act(() => call("DELETE", `/knowledge/${i.id}/pin`))}>Unpin</button> : null}
              <button className="btn ghost" onClick={() => act(() => call("POST", `/knowledge/${i.id}/restore`))}>Undo</button>
              <button className="btn ghost" onClick={async () => setHistory({ item: i, events: await get(`/knowledge/${i.id}/history`) })}>History</button>
              {i.status !== "retired" && <button className="btn ghost danger" onClick={() => act(() => call("POST", `/knowledge/${i.id}/retire`, { reason: "withdrawn by the owner" }))}>Withdraw</button>}
            </div>
          </li>
        ))}
      </ul>

      <div className="section-title" id="schedules"><h2>Reports sent to me regularly</h2></div>
      <ul className="list panel">
        {(schedules.data ?? []).length === 0 && <li className="empty">None. Choose “Send me this regularly” in a report's menu.</li>}
        {(schedules.data ?? []).map((s: any) => (
          <li key={s.id}>
            <div><div className="title">{s.question ?? "A report"}</div><div className="sub">{s.every}, next on {when(s.next_at)}</div></div>
            <div className="acts"><button className="btn ghost danger" onClick={() => act(() => call("DELETE", `/schedules/${s.id}`))}>Stop</button></div>
          </li>
        ))}
      </ul>

      <div className="section-title" id="shared"><h2>Shared knowledge my answers use</h2><p>{shared.length || "None yet"}</p></div>
      <ul className="list panel">
        {shared.length === 0 && <li className="empty">Nothing is shared with everyone yet.</li>}
        {shared.map((i: any) => (
          <li key={i.id}>
            <div>
              <div className="row" style={{ gap: 6 }}><span className="pill">{KIND[i.kind]}</span><span className="pill verified">{i.label}</span></div>
              <div className="title" style={{ marginTop: 6 }}>{i.title}</div>{i.body && <Md className="sub">{i.body}</Md>}
            </div>
            <div className="acts">{me?.is_admin && <button className="btn ghost" onClick={() => setEditing(i)}>Edit</button>}</div>
          </li>
        ))}
      </ul>

      <div className="section-title" id="requests"><h2>My requests</h2></div>
      <ul className="list panel">
        {(requests.data ?? []).length === 0 && <li className="empty">No requests. When a shared answer is wrong and you cannot change it, ask an admin from the report's menu.</li>}
        {(requests.data ?? []).map((r: any) => (
          <li key={r.id}>
            <div><Md className="title" >{r.text}</Md>{r.resolution && <div className="sub">Answer: <Md inline>{r.resolution}</Md></div>}<div className="sub small">{when(r.created_at)}</div></div>
            <span className={`pill ${r.status === "done" ? "verified" : r.status === "open" ? "yours" : "warn"}`}>{r.status === "open" ? "Waiting" : r.status === "done" ? "Done" : "Declined"}</span>
          </li>
        ))}
      </ul>

      {(editing || adding) && <EditItem item={editing} close={() => { setEditing(null); setAdding(false); refresh(); }} />}
      {history && (
        <Sheet title={`History of “${history.item.title}”`} close={() => setHistory(null)}>
          <ul className="list">
            {history.events.map((e: any) => (
              <li key={e.id}>
                <div><div className="title">{e.action.replace("status:", "now ")}</div><div className="sub">{e.actor}{e.note ? <>: <Md inline>{e.note}</Md></> : ""}</div></div>
                <span className="small muted">{when(e.at)}</span>
              </li>
            ))}
          </ul>
        </Sheet>
      )}
    </>
  );
}

function Lookup() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any | null>(null);
  return (
    <section style={{ marginTop: 18 }}>
      <form className="row" onSubmit={async (e) => { e.preventDefault(); if (q.trim()) setRes(await get(`/knowledge/about?q=${encodeURIComponent(q)}`)); }}>
        <input className="input" style={{ maxWidth: 520 }} aria-label="What does ReBo know about" placeholder="What does ReBo know about… (a word, a status, a table)" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn" type="submit"><Search />Look up</button>
      </form>
      {res && (
        <ul className="list panel" style={{ marginTop: 12 }}>
          {[...res.knowledge.verified, ...res.knowledge.yours, ...res.knowledge.pending].map((i: any) => (
            <li key={i.id}><div><div className="title">{i.title}</div><Md className="sub">{i.body}</Md></div><span className={`pill ${i.trust === "verified" ? "verified" : "yours"}`}>{KIND[i.kind]}</span></li>
          ))}
          {res.schema.map((t: any) => (
            <li key={`${t.table}.${t.column}`}><div><div className="title">{t.table}{t.column ? `.${t.column}` : ""}</div><div className="sub">{t.column_about || t.about}</div></div><span className="pill">{t.protected ? "Protected data" : "Data"}</span></li>
          ))}
          {res.values.map((v: any) => (
            <li key={`${v.table}.${v.column}.${v.value}`}><div><div className="title">{v.value}</div><div className="sub">stored in {v.table}.{v.column}, {v.freq} rows</div></div><span className="pill">Value</span></li>
          ))}
          {!res.schema.length && !res.values.length && !res.knowledge.verified.length && !res.knowledge.yours.length && <li className="empty">Nothing known about “{res.query}” yet.</li>}
        </ul>
      )}
    </section>
  );
}

function Defaults({ rows, onSaved }: { rows: any[]; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  return (
    <div className="panel">
      {rows.length > 0 && <ul className="list">{rows.map((d) => <li key={d.id}><div><div className="title">{d.name}</div><div className="sub">{d.value}</div></div><span /></li>)}</ul>}
      <form className="row" style={{ padding: 12, borderTop: rows.length ? "1px solid var(--line)" : 0 }} onSubmit={async (e) => {
        e.preventDefault();
        try { await call("PUT", `/defaults/${encodeURIComponent(name)}`, { value }); toast(`Default saved: ${name} = ${value}.`); setName(""); setValue(""); onSaved(); }
        catch (err) { toast((err as Error).message); }
      }}>
        <input className="input" style={{ maxWidth: 220 }} aria-label="Default name" placeholder="e.g. period" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input" style={{ maxWidth: 320 }} aria-label="Default value" placeholder="e.g. the last 30 days" value={value} onChange={(e) => setValue(e.target.value)} />
        <button className="btn" type="submit" disabled={!name.trim() || !value.trim()}>Save default</button>
      </form>
    </div>
  );
}

export function EditItem({ item, close }: { item: any | null; close: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ kind: item?.kind ?? "term", title: item?.title ?? "", question: item?.question ?? "", body: item?.body ?? "", sql: item?.sql ?? "" });
  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });
  return (
    <Sheet title={item ? `Edit “${item.title}”` : "Teach ReBo something"} close={close}
           intro={item ? "Changes are kept in the item's history and can be undone." : "It applies to your questions right away, and to others once it is shared."}>
      {!item && (
        <div className="field"><label htmlFor="kind">What is it?</label>
          <select id="kind" className="select" value={form.kind} onChange={set("kind")}>
            {Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      )}
      <div className="field"><label htmlFor="title">Name</label><input id="title" className="input" value={form.title} onChange={set("title")} /></div>
      {form.kind === "example" && <div className="field"><label htmlFor="question">The question it answers</label><input id="question" className="input" value={form.question} onChange={set("question")} /></div>}
      <div className="field"><label htmlFor="body">In plain words</label><textarea id="body" className="textarea" rows={3} value={form.body} onChange={set("body")} /></div>
      <div className="field"><label>Query or condition (optional)</label><CodeEditor lang="sql" label="Query or condition" rows={4} value={form.sql} onChange={(v) => setForm((f) => ({ ...f, sql: v }))} /></div>
      <div className="actions">
        <Button className="btn ghost" onPress={close}>Cancel</Button>
        <Button className="btn primary" isDisabled={!form.title.trim()} onPress={async () => {
          try {
            const res = item ? await call("PATCH", `/knowledge/${item.id}`, { title: form.title, question: form.question || null, body: form.body || null, sql: form.sql || null })
                             : await call("POST", "/knowledge", { kind: form.kind, title: form.title, question: form.question || null, body: form.body || null, sql: form.sql || null });
            toast(res.message ?? "Saved.");
            close();
          } catch (e) { toast((e as Error).message); }
        }}>{item ? "Save changes" : "Teach it"}</Button>
      </div>
    </Sheet>
  );
}
