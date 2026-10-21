// "You": who you are to ReBo, what you can do, your pinned and scheduled reports, how ReBo looks for
// you, and keyboard shortcuts. Locally it also switches who is signed in (behind the company login the
// proxy decides that).
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Keyboard, LogIn, Pin, Play, Timer } from "lucide-react";
import { useState } from "react";
import { Switch, ToggleButton, ToggleButtonGroup } from "react-aria-components";
import { Link, useNavigate } from "react-router";
import { get, identity, setIdentity, when, type Identity } from "../api";
import { setPrefs, usePrefs, type Prefs } from "../prefs";
import { ROLE, useMe } from "../shell";

const CAN: Record<string, string[]> = {
  user: ["Ask for any report in your own words", "Confirm or correct answers; ReBo remembers it for you",
         "Teach words, rules and defaults that apply to your questions", "Pin, schedule and download reports",
         "Ask an admin to fix something you cannot change"],
  admin: ["Everything a member can", "Review what people agree on and share it with everyone",
          "Edit, withdraw or undo any learned knowledge", "Answer people's requests", "See health, accuracy and cost"],
  owner: ["Everything an admin can", "Change the configuration, with a check before saving and a history to roll back"],
};

export default function MePage() {
  const me = useMe();
  const prefs = usePrefs();
  const navigate = useNavigate();
  const k = useQuery({ queryKey: ["knowledge"], queryFn: () => get<any>("/knowledge") });
  const conv = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations") });
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: () => get<any[]>("/schedules") });
  const mine: any[] = k.data?.mine ?? [];
  const pinned = mine.filter((i) => i.pinned && i.status !== "retired");
  const live = mine.filter((i) => i.status !== "retired");
  if (!me) return null;

  return (
    <div className="page">
      <section className="profile">
        <span className="avatar xl">{me.id.slice(0, 1)}</span>
        <div>
          <h1>{me.id}</h1>
          <p className="muted">{ROLE[me.role]}{me.team ? `, team ${me.team}` : ""}</p>
        </div>
        <div className="stats">
          <Stat n={conv.data?.length} label="conversations" />
          <Stat n={live.filter((i) => i.kind === "example").length} label="saved reports" />
          <Stat n={live.filter((i) => i.kind !== "example").length} label="things taught" />
          <Stat n={schedules.data?.length} label="scheduled" />
        </div>
      </section>

      <div className="grid2">
        <section className="card">
          <h2>What you can do</h2>
          <ul className="ticks">{(me.role === "user" ? CAN.user : me.role === "admin" ? CAN.admin : [...CAN.admin.slice(1), ...CAN.owner]).map((c) => <li key={c}>{c}</li>)}</ul>
          <Link className="more" to="/help">How to use ReBo<ArrowRight /></Link>
        </section>

        <section className="card" id="pinned">
          <h2><Pin />Pinned reports</h2>
          {pinned.length === 0 ? <p className="muted">Pin a report from its menu (⋯ → Pin to my start page) to run it from here with one click.</p> : (
            <ul className="rows">
              {pinned.map((i) => (
                <li key={i.id}><span>{i.title}</span>
                  <button className="btn small" onClick={() => navigate(`/?q=${encodeURIComponent(i.question || i.title)}`)}><Play />Run</button></li>
              ))}
            </ul>
          )}
        </section>

        <section className="card" id="scheduled">
          <h2><Timer />Sent to you regularly</h2>
          {(schedules.data ?? []).length === 0 ? <p className="muted">Choose “Send me this regularly” in a report's menu. It reruns the same query: no model, no cost.</p> : (
            <ul className="rows">{schedules.data!.map((s: any) => <li key={s.id}><span>{s.question ?? "A report"}</span><span className="muted small">{s.every}, next {when(s.next_at)}</span></li>)}</ul>
          )}
          <Link className="more" to="/knowledge#schedules">Manage<ArrowRight /></Link>
        </section>

        <section className="card" id="shortcuts">
          <h2><Keyboard />Shortcuts</h2>
          <dl className="keys">
            <dt><kbd>⌘</kbd><kbd>K</kbd></dt><dd>Search, ask or jump anywhere</dd>
            <dt><kbd>⌘</kbd><kbd>/</kbd></dt><dd>Your conversations</dd>
            <dt><kbd>Enter</kbd></dt><dd>Ask; <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line</dd>
            <dt><kbd>?</kbd></dt><dd>Help</dd>
            <dt><kbd>Esc</kbd></dt><dd>Close a sheet or dialog</dd>
          </dl>
        </section>
      </div>

      <section className="card" id="preferences">
        <h2>How ReBo looks for you</h2>
        <p className="muted small">Kept in this browser. It changes how answers look, never what they say.</p>
        <div className="prefs">
          <Choice label="Appearance" value={prefs.theme} set={(v) => setPrefs({ theme: v as Prefs["theme"] })}
                  options={[["auto", "Match my device"], ["light", "Light"], ["dark", "Dark"]]} />
          <Choice label="Table spacing" value={prefs.density} set={(v) => setPrefs({ density: v as Prefs["density"] })}
                  options={[["comfortable", "Comfortable"], ["compact", "Compact"]]} />
          <Toggle label="Shade every other row" hint="Easier to follow a row across wide tables" on={prefs.stripes} set={(v) => setPrefs({ stripes: v })} />
          <Toggle label="Show how I read your question" hint="Open under every answer; off folds it to one line" on={prefs.reading === "open"} set={(v) => setPrefs({ reading: v ? "open" : "folded" })} />
          <Toggle label="Open trends as a chart" hint="Answers by date or category start as a chart" on={prefs.chartFirst} set={(v) => setPrefs({ chartFirst: v })} />
          <Toggle label="Liquid Glass" hint="Off: solid bars, for less motion and more contrast" on={prefs.glass} set={(v) => setPrefs({ glass: v })} />
        </div>
      </section>

      <SignInAs />
    </div>
  );
}

function Stat({ n, label }: { n?: number; label: string }) {
  return <div className="stat"><b>{n ?? "–"}</b><span>{label}</span></div>;
}

function Choice({ label, value, set, options }: { label: string; value: string; set: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="pref">
      <span className="plabel">{label}</span>
      <ToggleButtonGroup aria-label={label} selectionMode="single" disallowEmptySelection className="segmented"
                         selectedKeys={[value]} onSelectionChange={(k) => set(String([...k][0]))}>
        {options.map(([k, l]) => <ToggleButton key={k} id={k}>{l}</ToggleButton>)}
      </ToggleButtonGroup>
    </div>
  );
}

function Toggle({ label, hint, on, set }: { label: string; hint: string; on: boolean; set: (v: boolean) => void }) {
  return (
    <Switch className="pref switch" isSelected={on} onChange={set}>
      <span className="plabel">{label}<small>{hint}</small></span>
      <span className="track" aria-hidden><span className="knob" /></span>
    </Switch>
  );
}

function SignInAs() {
  const current = identity();
  const me = useMe();
  const [user, setUser] = useState(current?.user ?? me?.id ?? "alice");
  const [role, setRole] = useState<Identity["role"]>(current?.role ?? me?.role ?? "user");
  return (
    <section className="card" id="sign-in">
      <h2><LogIn />Sign in as someone else</h2>
      <p className="muted small">For trying ReBo on your own machine. Behind your company's sign-in this is decided there and this has no effect.</p>
      <form className="row" onSubmit={(e) => { e.preventDefault(); setIdentity({ user: user.trim() || "alice", role }); }}>
        <input className="input" style={{ maxWidth: 220 }} aria-label="Name" value={user} onChange={(e) => setUser(e.target.value)} />
        <select className="select" style={{ maxWidth: 160 }} aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as Identity["role"])}>
          <option value="user">Member</option><option value="admin">Admin</option><option value="owner">Owner</option>
        </select>
        <button className="btn" type="submit">Switch</button>
      </form>
    </section>
  );
}
