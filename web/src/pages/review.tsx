import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "react-aria-components";
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
  const toggle = (id: string, on: boolean) => setPicked((p) => { const n = new Set(p); on ? n.add(id) : n.delete(id); return n; });
  const items = queue.data ?? [];

  return (
    <>
      <p className="lead">Review</p>
      <p className="intro">What people taught that is ready to be shared with everyone, and requests people cannot
        do themselves. Sharing makes an item apply to every answer; it can always be undone.</p>

      <div className="section-title">
        <h2>Waiting to be shared</h2><p>{items.length}</p><span className="spacer" />
        {items.length > 0 && (
          <div className="row">
            <input className="input" style={{ width: 300 }} aria-label="Note for the selected items" placeholder="Note kept in each item's history" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn primary" disabled={!picked.size} onClick={() => act(() => call("POST", "/review/bulk", { item_ids: [...picked], action: "share", note }))}>Share {picked.size || ""}</button>
            <button className="btn danger" disabled={!picked.size} onClick={() => act(() => call("POST", "/review/bulk", { item_ids: [...picked], action: "reject", note }))}>Withdraw {picked.size || ""}</button>
          </div>
        )}
      </div>
      <ul className="list panel">
        {items.length === 0 && <li className="empty"><Inbox size={22} />Nothing is waiting. Items arrive when an owner asks to share them, or when three people independently confirm the same report.</li>}
        {items.map((i) => (
          <li key={i.id} style={{ gridTemplateColumns: "28px minmax(0,1fr) auto" }}>
            <Checkbox className="row" aria-label={`Select ${i.title}`} isSelected={picked.has(i.id)} onChange={(on) => toggle(i.id, on)}>
              <span className="pill" style={{ padding: "3px 6px" }}>{picked.has(i.id) ? "✓" : " "}</span>
            </Checkbox>
            <div>
              <div className="row" style={{ gap: 6 }}><span className="pill">{i.kind}</span><span className="small muted">from {i.owner}, confirmed by {i.confirmers?.length ?? 0}, reported wrong {i.rejections}×</span></div>
              <div className="title" style={{ marginTop: 6 }}>{i.title}</div>
              {i.question && <div className="sub">Asked as “{i.question}”</div>}
              {i.body && <div className="sub">{i.body}</div>}
              {i.sql && <details className="query"><summary>Query</summary><pre className="code">{i.sql}</pre></details>}
            </div>
            <div className="acts">
              <button className="btn" onClick={() => act(() => call("POST", `/knowledge/${i.id}/promote`, { scope: "org" }))}>Share with everyone</button>
              {i.team && <button className="btn ghost" onClick={() => act(() => call("POST", `/knowledge/${i.id}/promote`, { scope: "team" }))}>Share with {i.team}</button>}
              <button className="btn ghost" onClick={() => setEditing(i)}>Edit first</button>
              <button className="btn ghost danger" onClick={() => act(() => call("POST", `/knowledge/${i.id}/retire`, { reason: "rejected in review" }))}>Withdraw</button>
            </div>
          </li>
        ))}
      </ul>

      <div className="section-title"><h2>Open requests</h2><p>{requests.data?.length ?? 0}</p></div>
      <ul className="list panel">
        {(requests.data ?? []).length === 0 && <li className="empty">No open requests.</li>}
        {(requests.data ?? []).map((r) => (
          <li key={r.id}>
            <div>
              <div className="row" style={{ gap: 6 }}><span className="pill yours">{r.kind.replace("_", " ")}</span><span className="small muted">{r.requester}, {when(r.created_at)}</span></div>
              <div className="title" style={{ fontWeight: 500, marginTop: 6 }}>{r.text}</div>
              <input className="input" style={{ marginTop: 10 }} aria-label="Answer to the requester" placeholder="Your answer, shown to the requester" value={answers[r.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [r.id]: e.target.value })} />
            </div>
            <div className="acts">
              <button className="btn primary" onClick={() => act(() => call("POST", `/requests/${r.id}/resolve`, { status: "done", resolution: answers[r.id] ?? "" }))}>Done</button>
              <button className="btn ghost danger" onClick={() => act(() => call("POST", `/requests/${r.id}/resolve`, { status: "declined", resolution: answers[r.id] ?? "" }))}>Decline</button>
            </div>
          </li>
        ))}
      </ul>
      {editing && <EditItem item={editing} close={() => { setEditing(null); refresh(); }} />}
    </>
  );
}
