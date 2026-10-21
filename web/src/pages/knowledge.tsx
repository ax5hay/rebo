import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "react-aria-components";
import { call, get, when } from "../api";
import { Sheet } from "../answer";
import { useMe, useToast } from "../shell";

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
  const refresh = () => { qc.invalidateQueries({ queryKey: ["knowledge"] }); qc.invalidateQueries({ queryKey: ["defaults"] }); qc.invalidateQueries({ queryKey: ["schedules"] }); };
  const act = async (fn: () => Promise<any>) => { try { const r = await fn(); if (r?.message) toast(r.message); refresh(); } catch (e) { toast((e as Error).message); } };

  return (
    <>
      <div className="pagehead">
        <h1>What I taught ReBo</h1>
        <p>Everything here shapes answers for you only, until it is shared with everyone. Nothing is deleted:
          every change has a history and can be undone.</p>
        <div className="actions"><button className="btn primary" onClick={() => setAdding(true)}>Teach something new</button></div>
      </div>
      {k.data?.notice && <div className="note bad" style={{ marginTop: 16 }}>{k.data.notice}</div>}

      <Lookup />

      <h2>My defaults</h2>
      <p className="soft small">Applied to every question unless it says otherwise, for example a period or a currency.</p>
      <Defaults rows={defaults.data ?? []} onSaved={refresh} />

      <h2>My saved knowledge</h2>
      <div className="ledger">
        {(k.data?.mine ?? []).length === 0 && <p className="empty">Nothing yet. Confirm a report with “Yes, this is right”, accept a “Remember this?” note, or teach something new.</p>}
        {(k.data?.mine ?? []).map((i: any) => (
          <div className="entry" key={i.id}>
            <div className="kind">{KIND[i.kind]}<span>{i.label}{i.pinned ? ", pinned" : ""}</span></div>
            <div>
              <div className="title">{i.title}</div>
              {i.question && <div className="body">Asked as: “{i.question}”</div>}
              {i.body && <div className="body">{i.body}</div>}
              {i.sql && <details><summary className="small">Query</summary><pre className="sql">{i.sql}</pre></details>}
              <div className="meta">Confirmed {i.confirmations} times, used {i.uses} times, reported wrong {i.rejections} times</div>
            </div>
            <div className="acts">
              <button className="btn quiet" onClick={() => setEditing(i)}>Edit</button>
              {i.status !== "verified" && i.status !== "retired" && <button className="btn quiet" onClick={() => act(() => call("POST", `/knowledge/${i.id}/share`))}>Share with everyone</button>}
              {i.pinned ? <button className="btn quiet" onClick={() => act(() => call("DELETE", `/knowledge/${i.id}/pin`))}>Unpin</button> : null}
              <button className="btn quiet" onClick={() => act(() => call("POST", `/knowledge/${i.id}/restore`))}>Undo last change</button>
              <button className="btn quiet" onClick={async () => setHistory({ item: i, events: await get(`/knowledge/${i.id}/history`) })}>History</button>
              {i.status !== "retired" && <button className="btn quiet danger" onClick={() => act(() => call("POST", `/knowledge/${i.id}/retire`, { reason: "withdrawn by the owner" }))}>Withdraw</button>}
            </div>
          </div>
        ))}
      </div>

      <h2>Reports sent to me regularly</h2>
      <div className="ledger">
        {(schedules.data ?? []).length === 0 && <p className="empty">None. Use “Send me this regularly” under a report.</p>}
        {(schedules.data ?? []).map((s: any) => (
          <div className="entry" key={s.id}>
            <div className="kind">Schedule<span>{s.every}</span></div>
            <div><div className="title">Next run {when(s.next_at)}</div></div>
            <div className="acts"><button className="btn quiet danger" onClick={() => act(() => call("DELETE", `/schedules/${s.id}`))}>Stop</button></div>
          </div>
        ))}
      </div>

      <h2>Shared knowledge my answers use</h2>
      <div className="ledger">
        {(k.data?.shared ?? []).length === 0 && <p className="empty">Nothing is shared yet.</p>}
        {(k.data?.shared ?? []).map((i: any) => (
          <div className="entry" key={i.id}>
            <div className="kind">{KIND[i.kind]}<span>{i.label}</span></div>
            <div><div className="title">{i.title}</div>{i.body && <div className="body">{i.body}</div>}</div>
            <div className="acts">{me?.is_admin && <button className="btn quiet" onClick={() => setEditing(i)}>Edit</button>}</div>
          </div>
        ))}
      </div>

      <h2>My requests</h2>
      <div className="ledger">
        {(requests.data ?? []).length === 0 && <p className="empty">No requests. When a shared answer is wrong and you cannot change it, use “Ask an admin to fix”.</p>}
        {(requests.data ?? []).map((r: any) => (
          <div className="entry" key={r.id}>
            <div className="kind">{r.status === "open" ? "Waiting" : r.status === "done" ? "Done" : "Declined"}<span>{when(r.created_at)}</span></div>
            <div><div className="body">{r.text}</div>{r.resolution && <div className="meta">Answer: {r.resolution}</div>}</div>
            <div />
          </div>
        ))}
      </div>

      {(editing || adding) && <EditItem item={editing} close={() => { setEditing(null); setAdding(false); refresh(); }} />}
      {history && (
        <Sheet title={`History of “${history.item.title}”`} close={() => setHistory(null)}>
          <div className="ledger">
            {history.events.map((e: any) => (
              <div className="entry" key={e.id}>
                <div className="kind">{e.action.replace("status:", "")}<span>{when(e.at)}</span></div>
                <div className="body">{e.actor}{e.note ? `: ${e.note}` : ""}</div>
                <div />
              </div>
            ))}
          </div>
        </Sheet>
      )}
    </>
  );
}

function Lookup() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any | null>(null);
  return (
    <section style={{ margin: "20px 0 8px" }}>
      <form className="row" onSubmit={async (e) => { e.preventDefault(); if (q.trim()) setRes(await get(`/knowledge/about?q=${encodeURIComponent(q)}`)); }}>
        <input className="input" style={{ maxWidth: 520 }} aria-label="What does ReBo know about" placeholder="What does ReBo know about…" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn" type="submit">Look up</button>
      </form>
      {res && (
        <div className="ledger" style={{ marginTop: 12 }}>
          {[...res.knowledge.verified, ...res.knowledge.yours, ...res.knowledge.pending].map((i: any) => (
            <div className="entry" key={i.id}><div className="kind">{KIND[i.kind]}<span>{i.trust}</span></div><div><div className="title">{i.title}</div><div className="body">{i.body}</div></div><div /></div>
          ))}
          {res.schema.map((t: any) => (
            <div className="entry" key={`${t.table}.${t.column}`}><div className="kind">Data<span>{t.protected ? "protected" : ""}</span></div><div><div className="title">{t.table}{t.column ? `.${t.column}` : ""}</div><div className="body">{t.column_about || t.about}</div></div><div /></div>
          ))}
          {res.values.map((v: any) => (
            <div className="entry" key={`${v.table}.${v.column}.${v.value}`}><div className="kind">Stored value<span>{v.freq} rows</span></div><div><div className="title">{v.value}</div><div className="body">in {v.table}.{v.column}</div></div><div /></div>
          ))}
          {!res.schema.length && !res.values.length && !res.knowledge.verified.length && !res.knowledge.yours.length && <p className="empty">Nothing known about “{res.query}” yet.</p>}
        </div>
      )}
    </section>
  );
}

function Defaults({ rows, onSaved }: { rows: any[]; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  return (
    <div className="ledger">
      {rows.map((d) => <div className="entry" key={d.id}><div className="kind">{d.name}</div><div className="title">{d.value}</div><div /></div>)}
      <form className="row" style={{ padding: "12px 0" }} onSubmit={async (e) => {
        e.preventDefault();
        try { await call("PUT", `/defaults/${encodeURIComponent(name)}`, { value }); toast(`Default saved: ${name} = ${value}.`); setName(""); setValue(""); onSaved(); }
        catch (err) { toast((err as Error).message); }
      }}>
        <input className="input" style={{ maxWidth: 220 }} aria-label="Default name" placeholder="for example: period" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input" style={{ maxWidth: 320 }} aria-label="Default value" placeholder="for example: the last 30 days" value={value} onChange={(e) => setValue(e.target.value)} />
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
    <Sheet title={item ? `Edit “${item.title}”` : "Teach ReBo something"} close={close}>
      {!item && (
        <div className="field"><label htmlFor="kind">What is it?</label>
          <select id="kind" className="input" value={form.kind} onChange={set("kind")}>
            {Object.entries(KIND).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      )}
      <div className="field" style={{ marginTop: 10 }}><label htmlFor="title">Name</label><input id="title" className="input" value={form.title} onChange={set("title")} /></div>
      {form.kind === "example" && <div className="field" style={{ marginTop: 10 }}><label htmlFor="question">The question it answers</label><input id="question" className="input" value={form.question} onChange={set("question")} /></div>}
      <div className="field" style={{ marginTop: 10 }}><label htmlFor="body">In plain words</label><textarea id="body" className="input" rows={3} value={form.body} onChange={set("body")} /></div>
      <div className="field" style={{ marginTop: 10 }}><label htmlFor="sql">Query or condition (optional)</label><textarea id="sql" className="input" rows={4} value={form.sql} onChange={set("sql")} /></div>
      <div className="row" style={{ marginTop: 14 }}>
        <Button className="btn primary" isDisabled={!form.title.trim()} onPress={async () => {
          try {
            const res = item ? await call("PATCH", `/knowledge/${item.id}`, { title: form.title, question: form.question || null, body: form.body || null, sql: form.sql || null })
                             : await call("POST", "/knowledge", { kind: form.kind, title: form.title, question: form.question || null, body: form.body || null, sql: form.sql || null });
            toast(res.message ?? "Saved.");
            close();
          } catch (e) { toast((e as Error).message); }
        }}>{item ? "Save changes" : "Teach it"}</Button>
        <Button className="btn quiet" onPress={close}>Cancel</Button>
      </div>
    </Sheet>
  );
}
