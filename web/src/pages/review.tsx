import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { call, get, when } from "../api";
import { useToast } from "../shell";
import { EditItem } from "./knowledge";

export default function ReviewPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const queue = useQuery({ queryKey: ["review"], queryFn: () => get<any[]>("/review") });
  const requests = useQuery({ queryKey: ["requests", "open"], queryFn: () => get<any[]>("/requests") });
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState<any | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const refresh = () => { qc.invalidateQueries({ queryKey: ["review"] }); qc.invalidateQueries({ queryKey: ["requests"] }); setPicked(new Set()); };
  const act = async (fn: () => Promise<any>) => { try { const r = await fn(); if (r?.message) toast(r.message); refresh(); } catch (e) { toast((e as Error).message); } };
  const toggle = (id: string) => setPicked((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  return (
    <>
      <div className="pagehead">
        <h1>Review</h1>
        <p>Things people taught that are ready to be shared with everyone, and requests people cannot do
          themselves. Sharing makes an item apply to every answer; it can always be undone.</p>
      </div>

      <h2>Waiting to be shared ({queue.data?.length ?? 0})</h2>
      {(queue.data?.length ?? 0) > 0 && (
        <div className="row" style={{ padding: "10px 0" }}>
          <input className="input" style={{ maxWidth: 420 }} aria-label="Note for the selected items" placeholder="A note kept in each item's history" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="btn primary" disabled={!picked.size} onClick={() => act(() => call("POST", "/review/bulk", { item_ids: [...picked], action: "share", note }))}>Share {picked.size || ""} with everyone</button>
          <button className="btn danger" disabled={!picked.size} onClick={() => act(() => call("POST", "/review/bulk", { item_ids: [...picked], action: "reject", note }))}>Withdraw {picked.size || ""}</button>
        </div>
      )}
      <div className="ledger">
        {(queue.data ?? []).length === 0 && <p className="empty">Nothing is waiting. Items arrive here when an owner asks to share them, or when three people independently confirm the same report.</p>}
        {(queue.data ?? []).map((i) => (
          <div className="entry" key={i.id}>
            <div className="kind">
              <label className="row"><input type="checkbox" checked={picked.has(i.id)} onChange={() => toggle(i.id)} aria-label={`Select ${i.title}`} />{i.kind}</label>
              <span>from {i.owner}</span>
            </div>
            <div>
              <div className="title">{i.title}</div>
              {i.question && <div className="body">Asked as “{i.question}”</div>}
              {i.body && <div className="body">{i.body}</div>}
              {i.sql && <pre className="sql">{i.sql}</pre>}
              <div className="meta">Confirmed by {i.confirmers?.length ?? 0} people, reported wrong {i.rejections} times</div>
            </div>
            <div className="acts">
              <button className="btn" onClick={() => act(() => call("POST", `/knowledge/${i.id}/promote`, { scope: "org" }))}>Share with everyone</button>
              {i.team && <button className="btn quiet" onClick={() => act(() => call("POST", `/knowledge/${i.id}/promote`, { scope: "team" }))}>Share with team {i.team}</button>}
              <button className="btn quiet" onClick={() => setEditing(i)}>Edit first</button>
              <button className="btn quiet danger" onClick={() => act(() => call("POST", `/knowledge/${i.id}/retire`, { reason: "rejected in review" }))}>Withdraw</button>
            </div>
          </div>
        ))}
      </div>

      <h2>Open requests ({requests.data?.length ?? 0})</h2>
      <div className="ledger">
        {(requests.data ?? []).length === 0 && <p className="empty">No open requests.</p>}
        {(requests.data ?? []).map((r) => (
          <div className="entry" key={r.id}>
            <div className="kind">{r.kind.replace("_", " ")}<span>{r.requester}, {when(r.created_at)}</span></div>
            <div>
              <div className="body">{r.text}</div>
              <input className="input" style={{ marginTop: 8 }} aria-label="Answer to the requester" placeholder="Your answer, shown to the requester" value={answers[r.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [r.id]: e.target.value })} />
            </div>
            <div className="acts">
              <button className="btn" onClick={() => act(() => call("POST", `/requests/${r.id}/resolve`, { status: "done", resolution: answers[r.id] ?? "" }))}>Done</button>
              <button className="btn quiet danger" onClick={() => act(() => call("POST", `/requests/${r.id}/resolve`, { status: "declined", resolution: answers[r.id] ?? "" }))}>Decline</button>
            </div>
          </div>
        ))}
      </div>
      {editing && <EditItem item={editing} close={() => { setEditing(null); refresh(); }} />}
    </>
  );
}
