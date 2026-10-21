// Knowledge: everything ReBo learned from you, and the shared knowledge your answers use. Tabs keep it
// to one screen at a time (each tab has an anchor, so Help can link to it); each item is a card with one
// main action and the rest in a menu; nothing is deleted, every change has a history and an undo.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck, CalendarClock, CircleCheck, Database, Flag, History, Inbox, Pencil, PinOff, Plus, Repeat, Search, Share2, SlidersHorizontal,
  Undo2, Users, X, XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button, Radio, RadioGroup, ToggleButton, ToggleButtonGroup } from "react-aria-components";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import { call, get, plural, when } from "../api";
import { Sheet } from "../answer";
import { CodeEditor, SqlCode } from "../code";
import { Md } from "../md";
import { useMe, useToast } from "../shell";
import { Empty, KINDS, KindIcon, MoreMenu, PageHead, Timeline, type MenuAction } from "../ui";

const TABS = [
  { id: "saved", label: "Yours" },
  { id: "shared", label: "Shared with everyone" },
  { id: "defaults", label: "My defaults" },
  { id: "schedules", label: "Scheduled" },
  { id: "requests", label: "My requests" },
] as const;
type Tab = (typeof TABS)[number]["id"];

const STATUS: Record<string, [string, string]> = {
  active: ["Only you", "yours"], proposed: ["Waiting for an admin", "warn"], verified: ["Shared with everyone", "verified"],
  stale: ["Needs a re-check", "warn"], retired: ["Withdrawn", ""],
};

export default function KnowledgePage() {
  const me = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const k = useQuery({ queryKey: ["knowledge"], queryFn: () => get<any>("/knowledge") });
  const defaults = useQuery({ queryKey: ["defaults"], queryFn: () => get<any[]>("/defaults") });
  const requests = useQuery({ queryKey: ["requests", "mine"], queryFn: () => get<any[]>("/requests?status=") });
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: () => get<any[]>("/schedules") });
  const [editing, setEditing] = useState<any | null>(null);
  const [adding, setAdding] = useState(params.get("teach") === "1");
  const [history, setHistory] = useState<any | null>(null);
  const [kind, setKind] = useState("all");
  const [showRetired, setShowRetired] = useState(false);
  const tab: Tab = (TABS.find((t) => `#${t.id}` === hash)?.id ?? "saved") as Tab;
  const setTab = (t: string) => navigate({ hash: t === "saved" ? "" : t }, { replace: true });
  useEffect(() => { if (params.get("teach")) { setParams({}, { replace: true }); setAdding(true); } }, [params, setParams]);

  const refresh = () => ["knowledge", "defaults", "schedules", "requests"].forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
  const act = async (fn: () => Promise<any>) => { try { const r = await fn(); if (r?.message) toast(r.message); refresh(); } catch (e) { toast((e as Error).message); } };
  const mine: any[] = k.data?.mine ?? [];
  const shared: any[] = k.data?.shared ?? [];
  const live = mine.filter((i) => i.status !== "retired");
  const shown = useMemo(() => mine.filter((i) => (showRetired || i.status !== "retired") && (kind === "all" || i.kind === kind)), [mine, kind, showRetired]);
  const waiting = (requests.data ?? []).filter((r) => r.status === "open").length;
  const counts: Record<Tab, number | undefined> = { saved: live.length, shared: shared.length, defaults: defaults.data?.length,
                                                     schedules: schedules.data?.length, requests: requests.data?.length };

  const itemAction = async (i: any, id: string) => {
    if (id === "share") await act(() => call("POST", `/knowledge/${i.id}/share`));
    if (id === "unpin") await act(() => call("DELETE", `/knowledge/${i.id}/pin`));
    if (id === "undo") await act(() => call("POST", `/knowledge/${i.id}/restore`));
    if (id === "history") setHistory({ item: i, events: await get(`/knowledge/${i.id}/history`) });
    if (id === "withdraw") await act(() => call("POST", `/knowledge/${i.id}/retire`, { reason: "withdrawn by the owner" }));
  };
  const menuFor = (i: any): MenuAction[] => [
    ...(i.status !== "verified" && i.status !== "retired" ? [{ id: "share", label: "Ask to share with everyone", icon: Share2 }] : []),
    ...(i.pinned ? [{ id: "unpin", label: "Unpin from my start page", icon: PinOff }] : []),
    { id: "history", label: "History", icon: History },
    { id: "undo", label: "Undo the last change", icon: Undo2 },
    ...(i.status !== "retired" ? [{ id: "withdraw", label: "Withdraw", icon: XCircle, danger: true, separator: true }] : []),
  ];

  return (
    <div className="page">
      <PageHead title="Knowledge"
        lede="What ReBo learned from you shapes your answers right away; it reaches others only once it is shared. Nothing is deleted, and every change can be undone."
        actions={<button className="btn primary" onClick={() => setAdding(true)}><Plus />Teach something new</button>}
        stats={[
          { n: live.filter((i) => i.kind === "example").length, label: "Saved reports" },
          { n: live.filter((i) => i.kind !== "example").length, label: "Words, rules, joins" },
          { n: shared.length, label: "Shared with everyone" },
          { n: waiting, label: "Requests waiting", tone: waiting ? "warn" : undefined },
        ]} />
      {k.data?.notice && <div className="banner warn"><Flag /><Md inline>{k.data.notice}</Md></div>}

      <Lookup />

      <nav className="tabbar" aria-label="Knowledge sections">
        {TABS.map((t) => (
          <button key={t.id} id={t.id} className={tab === t.id ? "on" : ""} aria-current={tab === t.id ? "page" : undefined} onClick={() => setTab(t.id)}>
            {t.label}{counts[t.id] ? <span className="count">{counts[t.id]}</span> : null}
          </button>
        ))}
      </nav>

      {tab === "saved" && (
        <>
          <div className="filterrow">
            <ToggleButtonGroup aria-label="Kind" selectionMode="single" disallowEmptySelection className="segmented small" selectedKeys={[kind]}
                               onSelectionChange={(s) => setKind(String([...s][0]))}>
              <ToggleButton id="all">All</ToggleButton>
              {Object.entries(KINDS).map(([id, v]) => <ToggleButton key={id} id={id}>{v.label}</ToggleButton>)}
            </ToggleButtonGroup>
            <label className="check"><input type="checkbox" checked={showRetired} onChange={(e) => setShowRetired(e.target.checked)} />Show withdrawn</label>
          </div>
          {shown.length === 0 ? (
            <div className="panel">
              <Empty icon={BadgeCheck} title={mine.length ? "Nothing of this kind" : "Nothing taught yet"}
                     action={<button className="btn primary" onClick={() => setAdding(true)}><Plus />Teach something new</button>}>
                Press “Yes, this is right” under an answer, accept a “Remember this?” note, or teach ReBo a word or rule here.
              </Empty>
            </div>
          ) : (
            <ul className="cards">
              {shown.map((i) => (
                <ItemCard key={i.id} i={i}
                  actions={<><button className="btn small" onClick={() => setEditing(i)}><Pencil />Edit</button>
                    <MoreMenu label={`More for ${i.title}`} actions={menuFor(i)} onAction={(id) => itemAction(i, id)} /></>} />
              ))}
            </ul>
          )}
        </>
      )}

      {tab === "shared" && (shared.length === 0 ? (
        <div className="panel"><Empty icon={Users} title="Nothing shared yet">When three people agree on the same thing and an admin approves it, it appears here and shapes everyone's answers.</Empty></div>
      ) : (
        <ul className="cards">{shared.map((i) => <ItemCard key={i.id} i={i} actions={me?.is_admin ? <button className="btn small" onClick={() => setEditing(i)}><Pencil />Edit</button> : null} />)}</ul>
      ))}

      {tab === "defaults" && <Defaults rows={defaults.data ?? []} onChange={refresh} />}

      {tab === "schedules" && ((schedules.data ?? []).length === 0 ? (
        <div className="panel"><Empty icon={CalendarClock} title="Nothing scheduled">Open a report's ⋯ menu and choose “Send me this regularly”. It reruns the same query on that day's data, with no model and no cost.</Empty></div>
      ) : (
        <ul className="cards">
          {schedules.data!.map((s: any) => (
            <li key={s.id} className="itemcard">
              <span className="kindicon green" aria-hidden><CalendarClock /></span>
              <div className="itembody"><div className="itemtitle">{s.question ?? "A report"}</div><div className="meta"><span>{s.every}</span><span>next {when(s.next_at)}</span></div></div>
              <div className="itemactions"><button className="btn small danger" onClick={() => act(() => call("DELETE", `/schedules/${s.id}`))}><X />Stop</button></div>
            </li>
          ))}
        </ul>
      ))}

      {tab === "requests" && ((requests.data ?? []).length === 0 ? (
        <div className="panel"><Empty icon={Inbox} title="No requests">When a shared answer is wrong and you cannot change it yourself, choose ⋯ → “Ask an admin to fix this” under the report.</Empty></div>
      ) : (
        <ul className="cards">
          {requests.data!.map((r: any) => (
            <li key={r.id} className="itemcard">
              <span className={`kindicon ${r.status === "done" ? "green" : r.status === "open" ? "indigo" : "brass"}`} aria-hidden><Flag /></span>
              <div className="itembody">
                <Md className="itemtitle">{r.text}</Md>
                {r.resolution && <blockquote className="reply"><b>Answer:</b> <Md inline>{r.resolution}</Md></blockquote>}
                <div className="meta"><span>{when(r.created_at)}</span></div>
              </div>
              <span className={`pill ${r.status === "done" ? "verified" : r.status === "open" ? "yours" : "warn"}`}>{r.status === "open" ? "Waiting" : r.status === "done" ? "Done" : "Declined"}</span>
            </li>
          ))}
        </ul>
      ))}

      {(editing || adding) && <EditItem item={editing} close={() => { setEditing(null); setAdding(false); refresh(); }} />}
      {history && (
        <Sheet icon={History} title={history.item.title} intro="Every change, newest first. Undo puts back the previous version." close={() => setHistory(null)}>
          <Timeline events={[...history.events].reverse()} />
          <div className="actions"><Button className="btn" onPress={async () => { await itemAction(history.item, "undo"); setHistory(null); }}><Undo2 />Undo the last change</Button></div>
        </Sheet>
      )}
    </div>
  );
}

export function ItemCard({ i, actions, select }: { i: any; actions?: React.ReactNode; select?: React.ReactNode }) {
  const [label, tone] = STATUS[i.status] ?? [i.label ?? i.status, ""];
  return (
    <li className={`itemcard${i.status === "retired" ? " retired" : ""}`}>
      {select}
      <KindIcon kind={i.kind} />
      <div className="itembody">
        <div className="itemhead">
          <span className="itemtitle">{i.title}</span>
          <span className={`pill ${tone}`}>{i.label && i.status === "verified" ? i.label : label}</span>
          {i.pinned ? <span className="pill yours">Pinned</span> : null}
        </div>
        {i.question && <div className="asked">Asked as “{i.question}”</div>}
        {i.body && <Md className="itemtext">{i.body}</Md>}
        <div className="meta">
          <span>{KINDS[i.kind]?.label ?? i.kind}</span>
          {i.confirmations != null && <span title="Confirmed"><CircleCheck />{plural(i.confirmations, "confirmation", "confirmations")}</span>}
          {i.uses != null && <span title="Used in answers"><Repeat />used {i.uses}×</span>}
          {i.rejections ? <span className="warn" title="Reported wrong"><Flag />reported wrong {i.rejections}×</span> : null}
        </div>
        {i.sql && <details className="query"><summary><Database size={14} />Query</summary><SqlCode sql={i.sql} /></details>}
      </div>
      {actions && <div className="itemactions">{actions}</div>}
    </li>
  );
}

function Lookup() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const found = res ? [...res.knowledge.verified, ...res.knowledge.yours, ...res.knowledge.pending] : [];
  return (
    <section className="lookup">
      <form onSubmit={async (e) => { e.preventDefault(); if (!q.trim()) return; setBusy(true); try { setRes(await get(`/knowledge/about?q=${encodeURIComponent(q)}`)); } finally { setBusy(false); } }}>
        <Search />
        <input aria-label="What does ReBo know about" placeholder="What does ReBo know about… a word, a status, a table" value={q} onChange={(e) => { setQ(e.target.value); if (!e.target.value) setRes(null); }} />
        {res && <button type="button" className="iconbtn" aria-label="Clear" onClick={() => { setQ(""); setRes(null); }}><X /></button>}
        <button className="btn small" type="submit" disabled={!q.trim() || busy}>Look up</button>
      </form>
      {res && (
        <div className="lookupres">
          {found.length > 0 && <><h3>Learned</h3><ul className="rows">{found.map((i: any) => <li key={i.id}><span><b>{i.title}</b>{i.body ? <>: <Md inline>{i.body}</Md></> : null}</span><span className={`pill ${i.trust === "verified" ? "verified" : "yours"}`}>{KINDS[i.kind]?.label}</span></li>)}</ul></>}
          {res.schema.length > 0 && <><h3>In the database</h3><ul className="rows">{res.schema.map((t: any) => <li key={`${t.table}.${t.column}`}><span><code>{t.table}{t.column ? `.${t.column}` : ""}</code> {t.column_about || t.about}</span><span className="pill">{t.protected ? "Protected" : t.column ? "Column" : "Table"}</span></li>)}</ul></>}
          {res.values.length > 0 && <><h3>Stored values</h3><ul className="rows">{res.values.map((v: any) => <li key={`${v.table}.${v.column}.${v.value}`}><span><b>{v.value}</b> in <code>{v.table}.{v.column}</code></span><span className="muted small">{plural(v.freq, "row", "rows")}</span></li>)}</ul></>}
          {!found.length && !res.schema.length && !res.values.length && <p className="muted">Nothing known about “{res.query}” yet. Teach it, or ask a question that uses it.</p>}
        </div>
      )}
    </section>
  );
}

function Defaults({ rows, onChange }: { rows: any[]; onChange: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  return (
    <div className="panel defaults">
      <div className="defaultsintro"><SlidersHorizontal /><p>A default fills in what you usually mean when a question does not say, like a period or a place. Each answer lists the defaults it used.</p></div>
      {rows.length > 0 && (
        <ul className="rows">
          {rows.map((d) => (
            <li key={d.id}><span className="defrow"><b>{d.name}</b><span className="muted">means</span><span>{d.value}</span></span>
              <button className="btn small ghost danger" onClick={async () => { try { await call("POST", `/knowledge/${d.id}/retire`, { reason: "default removed" }); toast(`Default removed: ${d.name}.`); onChange(); } catch (e) { toast((e as Error).message); } }}><X />Remove</button></li>
          ))}
        </ul>
      )}
      <form className="sentence" onSubmit={async (e) => {
        e.preventDefault();
        try { await call("PUT", `/defaults/${encodeURIComponent(name.trim())}`, { value }); toast(`Default saved: ${name} means ${value}.`); setName(""); setValue(""); onChange(); }
        catch (err) { toast((err as Error).message); }
      }}>
        <span>When I don't say</span>
        <input className="input" aria-label="Default name" placeholder="the period" value={name} onChange={(e) => setName(e.target.value)} />
        <span>assume</span>
        <input className="input" aria-label="Default value" placeholder="the last 30 days" value={value} onChange={(e) => setValue(e.target.value)} />
        <button className="btn primary" type="submit" disabled={!name.trim() || !value.trim()}>Save default</button>
      </form>
    </div>
  );
}

const TEACH: Record<string, { name: string; namePh: string; body: string; bodyPh: string; sql: string; sqlPh: string; sqlOpen: boolean }> = {
  term: { name: "The word or phrase", namePh: "on hold", body: "What it means", bodyPh: "A customer whose status is paused", sql: "As a condition (optional)", sqlPh: "status = 'paused'", sqlOpen: false },
  note: { name: "The rule, in a few words", namePh: "Test accounts", body: "In plain words", bodyPh: "Accounts whose email ends in @example.com are tests and never count", sql: "As a condition (optional)", sqlPh: "email NOT LIKE '%@example.com'", sqlOpen: false },
  example: { name: "Report name", namePh: "Paused customers", body: "Notes (optional)", bodyPh: "Excludes test accounts", sql: "The query", sqlPh: "SELECT …", sqlOpen: true },
  join: { name: "Tables", namePh: "orders to customers", body: "In plain words", bodyPh: "Each order belongs to one customer", sql: "The join condition", sqlPh: "orders.customer_id = customer.customer_id", sqlOpen: true },
};

export function EditItem({ item, close }: { item: any | null; close: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ kind: item?.kind ?? "term", title: item?.title ?? "", question: item?.question ?? "", body: item?.body ?? "", sql: item?.sql ?? "" });
  const t = TEACH[form.kind] ?? TEACH.note;
  const [sqlOpen, setSqlOpen] = useState(!!item?.sql);
  const set = (key: string) => (e: any) => setForm({ ...form, [key]: e.target.value });
  const save = async () => {
    try {
      const body = { title: form.title, question: form.question || null, body: form.body || null, sql: form.sql || null };
      const res = item ? await call("PATCH", `/knowledge/${item.id}`, body) : await call("POST", "/knowledge", { kind: form.kind, ...body });
      toast(res.message ?? "Saved.");
      close();
    } catch (e) { toast((e as Error).message); }
  };
  return (
    <Sheet wide icon={item ? Pencil : Plus} title={item ? `Edit “${item.title}”` : "Teach ReBo something"} close={close}
           intro={item ? "Your change is kept in the item's history and can be undone." : "It shapes your own answers right away. Others get it once it is shared."}>
      {!item ? (
        <RadioGroup aria-label="What is it?" className="kindpick" value={form.kind} onChange={(v) => { setForm({ ...form, kind: v }); setSqlOpen(TEACH[v].sqlOpen); }}>
          {Object.entries(KINDS).map(([id, v]) => (
            <Radio key={id} value={id} className="kindcard">
              <KindIcon kind={id} size={34} /><span><b>{v.label}</b><small>{v.one}</small></span>
            </Radio>
          ))}
        </RadioGroup>
      ) : <div className="row" style={{ marginBottom: 4 }}><KindIcon kind={form.kind} size={28} /><b>{KINDS[form.kind]?.label}</b></div>}
      <div className="field"><label htmlFor="title">{t.name}</label><input id="title" className="input" placeholder={t.namePh} value={form.title} onChange={set("title")} autoFocus={!!item} /></div>
      {form.kind === "example" && <div className="field"><label htmlFor="question">The question it answers</label><input id="question" className="input" placeholder="Which customers are paused?" value={form.question} onChange={set("question")} /></div>}
      <div className="field"><label htmlFor="body">{t.body}</label><textarea id="body" className="textarea" rows={3} placeholder={t.bodyPh} value={form.body} onChange={set("body")} /></div>
      {sqlOpen || t.sqlOpen ? (
        <div className="field"><label>{t.sql}</label><CodeEditor lang="sql" label={t.sql} rows={4} value={form.sql} onChange={(v) => setForm((f) => ({ ...f, sql: v }))} /><span className="hint">For example <code>{t.sqlPh}</code></span></div>
      ) : (
        <button type="button" className="addlink" onClick={() => setSqlOpen(true)}><Plus />Add it as a condition too (optional)</button>
      )}
      <div className="actions spread">
        <span className="scope"><Users />{item?.status === "verified" ? "Shared: this changes everyone's answers" : "Only you, until it is shared"}</span>
        <div className="row">
          <Button className="btn ghost" onPress={close}>Cancel</Button>
          <Button className="btn primary" isDisabled={!form.title.trim()} onPress={save}>{item ? "Save changes" : "Teach it"}</Button>
        </div>
      </div>
    </Sheet>
  );
}
