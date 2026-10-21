// Review (admins): what people agree on, waiting to be shared with everyone, and requests people cannot
// handle themselves. Each item shows its evidence first (who taught it, how many confirmed it, how often
// it was reported wrong). Selecting items brings up a floating glass bar for acting on several at once.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleCheck, Flag, Inbox, MessageSquareReply, Pencil, Share2, Users, X, XCircle } from "lucide-react";
import { useState } from "react";
import { Checkbox } from "react-aria-components";
import { useLocation, useNavigate } from "react-router";
import { call, get, plural, when } from "../api";
import { Glass } from "../glass";
import { Md } from "../md";
import { useToast } from "../shell";
import { Empty, MoreMenu, PageHead } from "../ui";
import { EditItem, ItemCard } from "./knowledge";

export default function ReviewPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const queue = useQuery({ queryKey: ["review"], queryFn: () => get<any[]>("/review") });
  const requests = useQuery({ queryKey: ["requests", "open"], queryFn: () => get<any[]>("/requests") });
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState<any | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const refresh = () => { qc.invalidateQueries({ queryKey: ["review"] }); qc.invalidateQueries({ queryKey: ["requests"] }); setPicked(new Set()); setNote(""); };
  const act = async (fn: () => Promise<any>) => { try { const r = await fn(); if (r?.message) toast(r.message); refresh(); } catch (e) { toast((e as Error).message); } };
  const toggle = (id: string, on: boolean) => setPicked((p) => { const n = new Set(p); if (on) n.add(id); else n.delete(id); return n; });
  const items = queue.data ?? [];
  const reqs = requests.data ?? [];
  const tab = hash === "#requests" ? "requests" : "queue";

  return (
    <div className="page">
      <PageHead title="Review"
        lede="What people taught that is ready for everyone, and requests they cannot handle themselves. Sharing makes an item shape every answer; it can always be undone."
        stats={[
          { n: items.length, label: "Waiting to be shared", tone: items.length ? "warn" : undefined },
          { n: reqs.length, label: "Open requests", tone: reqs.length ? "warn" : undefined },
        ]} />

      <nav className="tabbar" aria-label="Review sections">
        <button className={tab === "queue" ? "on" : ""} onClick={() => navigate({ hash: "" }, { replace: true })}>Waiting to be shared{items.length ? <span className="count">{items.length}</span> : null}</button>
        <button className={tab === "requests" ? "on" : ""} onClick={() => navigate({ hash: "requests" }, { replace: true })}>Requests{reqs.length ? <span className="count">{reqs.length}</span> : null}</button>
      </nav>

      {tab === "queue" && (items.length === 0 ? (
        <div className="panel"><Empty icon={Inbox} title="Nothing is waiting">Items arrive when an owner asks to share them, or when three people independently confirm the same report.</Empty></div>
      ) : (
        <>
          <div className="filterrow">
            <label className="check"><input type="checkbox" checked={picked.size === items.length} onChange={(e) => setPicked(e.target.checked ? new Set(items.map((i) => i.id)) : new Set())} />Select all</label>
          </div>
          <ul className="cards">
            {items.map((i) => (
              <ItemCard key={i.id} i={{ ...i, confirmations: i.confirmers?.length ?? 0 }}
                select={<Checkbox className="pick" aria-label={`Select ${i.title}`} isSelected={picked.has(i.id)} onChange={(on) => toggle(i.id, on)}><span className="box"><Check /></span></Checkbox>}
                actions={<>
                  <button className="btn small primary" onClick={() => act(() => call("POST", `/knowledge/${i.id}/promote`, { scope: "org" }))}><Share2 />Share</button>
                  <MoreMenu label={`More for ${i.title}`} onAction={(id) => {
                    if (id === "team") act(() => call("POST", `/knowledge/${i.id}/promote`, { scope: "team" }));
                    if (id === "edit") setEditing(i);
                    if (id === "withdraw") act(() => call("POST", `/knowledge/${i.id}/retire`, { reason: "rejected in review" }));
                  }} actions={[
                    ...(i.team ? [{ id: "team", label: `Share with ${i.team} only`, icon: Users }] : []),
                    { id: "edit", label: "Edit before sharing", icon: Pencil },
                    { id: "withdraw", label: "Withdraw", icon: XCircle, danger: true, separator: true },
                  ]} />
                </>} />
            ))}
          </ul>
          <p className="footnote"><CircleCheck />Confirmations count different people only. Sharing and withdrawing can both be undone from the item's history.</p>
        </>
      ))}

      {tab === "requests" && (reqs.length === 0 ? (
        <div className="panel"><Empty icon={MessageSquareReply} title="No open requests">People ask from a report's ⋯ menu when something shared is wrong and they cannot change it.</Empty></div>
      ) : (
        <ul className="cards">
          {reqs.map((r) => (
            <li key={r.id} className="itemcard request">
              <span className="avatar">{r.requester.slice(0, 1)}</span>
              <div className="itembody">
                <div className="itemhead"><span className="itemtitle">{r.requester}</span><span className="pill yours"><Flag size={12} />{r.kind.replace("_", " ")}</span><span className="muted small">{when(r.created_at)}</span></div>
                <Md className="itemtext big">{r.text}</Md>
                <textarea className="textarea" rows={2} aria-label="Answer to the requester" placeholder="Your answer, shown to them under My requests"
                          value={answers[r.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [r.id]: e.target.value })} />
                <div className="row" style={{ marginTop: 10 }}>
                  <button className="btn small primary" onClick={() => act(() => call("POST", `/requests/${r.id}/resolve`, { status: "done", resolution: answers[r.id] ?? "" }))}><Check />Done</button>
                  <button className="btn small ghost danger" onClick={() => act(() => call("POST", `/requests/${r.id}/resolve`, { status: "declined", resolution: answers[r.id] ?? "" }))}><X />Decline</button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ))}

      {picked.size > 0 && (
        <Glass className="bulkbar" role="toolbar" aria-label="Selected items">
          <span className="bulkcount">{plural(picked.size, "item", "items")} selected</span>
          <input className="input" aria-label="Note for the selected items" placeholder="Note kept in each item's history" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="btn primary" onClick={() => act(() => call("POST", "/review/bulk", { item_ids: [...picked], action: "share", note }))}><Share2 />Share</button>
          <button className="btn danger" onClick={() => act(() => call("POST", "/review/bulk", { item_ids: [...picked], action: "reject", note }))}><XCircle />Withdraw</button>
          <button className="iconbtn" aria-label="Clear the selection" onClick={() => setPicked(new Set())}><X /></button>
        </Glass>
      )}
      {editing && <EditItem item={editing} close={() => { setEditing(null); refresh(); }} />}
    </div>
  );
}
