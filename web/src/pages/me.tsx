// "You": who you are to ReBo, your pinned and scheduled reports, how ReBo looks for you, what you can do,
// keyboard shortcuts, and (locally) who is signed in. Laid out like a settings app: an identity card,
// a glass rail of sections, and grouped lists of uniform rows, so the page reads as one surface.
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight, CalendarClock, Check, Keyboard, LogIn, MessagesSquare, Palette, Pin, Play, Plus, ShieldCheck, Sparkles, SquarePen, Timer, type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Switch, ToggleButton, ToggleButtonGroup } from "react-aria-components";
import { Link, useNavigate } from "react-router";
import { displayName, get, identity, personId, setIdentity, when, type Identity } from "../api";
import { useDemo } from "../demo";
import { Glass } from "../glass";
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

const SECTIONS: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "pinned", label: "Pinned", icon: Pin },
  { id: "scheduled", label: "Sent to you", icon: Timer },
  { id: "preferences", label: "Appearance", icon: Palette },
  { id: "abilities", label: "What you can do", icon: ShieldCheck },
  { id: "shortcuts", label: "Shortcuts", icon: Keyboard },
  { id: "sign-in", label: "Signed in as", icon: LogIn },
];

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
  const can = me.role === "user" ? CAN.user : me.role === "admin" ? CAN.admin : [...CAN.admin.slice(1), ...CAN.owner];
  const run = (q: string) => navigate(`/?q=${encodeURIComponent(q)}`);

  return (
    <div className="page you">
      <Glass as="section" className="idcard" aria-label="Your profile" strength={34}>
        <span className="halo" aria-hidden><span className="avatar xl">{me.id.slice(0, 1)}</span></span>
        <div className="who">
          <h1>{displayName(me.id)}</h1>
          <p><span className="rolechip">{ROLE[me.role]}</span>{me.team ? <span className="muted">team {me.team}</span> : null}</p>
        </div>
        <div className="quick">
          <Link className="btn ghostglass" to="/"><SquarePen />New question</Link>
          <Link className="btn ghostglass" to="/knowledge?teach=1"><Plus />Teach ReBo</Link>
        </div>
        <dl className="figs">
          <Fig n={conv.data?.length} label="Conversations" icon={MessagesSquare} />
          <Fig n={live.filter((i) => i.kind === "example").length} label="Saved reports" icon={Sparkles} />
          <Fig n={live.filter((i) => i.kind !== "example").length} label="Things taught" icon={Check} />
          <Fig n={schedules.data?.length} label="Scheduled" icon={CalendarClock} />
        </dl>
      </Glass>

      <div className="yougrid">
        <Rail />
        <div className="groups">
          <Group id="pinned" title="Pinned reports" note="One click runs them on today's data.">
            {pinned.length === 0
              ? <Row muted>Pin a report from its ⋯ menu and it appears here and on your start page.</Row>
              : pinned.map((i) => (
                <Row key={i.id} label={i.title}>
                  <button className="btn small ghostglass" onClick={() => run(i.question || i.title)}><Play />Run</button>
                </Row>
              ))}
          </Group>

          <Group id="scheduled" title="Sent to you regularly" note="The same query runs again on that day's data: no model, no cost."
                 footer={<Link className="more" to="/knowledge#schedules">Manage schedules<ArrowRight /></Link>}>
            {(schedules.data ?? []).length === 0
              ? <Row muted>Choose “Send me this regularly” in a report's ⋯ menu.</Row>
              : schedules.data!.map((s: any) => <Row key={s.id} label={s.question ?? "A report"}><span className="value">{s.every}, next {when(s.next_at)}</span></Row>)}
          </Group>

          <Group id="preferences" title="How ReBo looks for you" note="Kept in this browser. It changes how answers look, never what they say.">
            <Row label="Appearance">
              <Seg label="Appearance" value={prefs.theme} set={(v) => setPrefs({ theme: v as Prefs["theme"] })}
                   options={[["auto", "Auto"], ["light", "Light"], ["dark", "Dark"]]} />
            </Row>
            <Row label="Table spacing">
              <Seg label="Table spacing" value={prefs.density} set={(v) => setPrefs({ density: v as Prefs["density"] })}
                   options={[["comfortable", "Comfortable"], ["compact", "Compact"]]} />
            </Row>
            <Toggle label="Shade every other row" hint="Easier to follow a row across wide tables" on={prefs.stripes} set={(v) => setPrefs({ stripes: v })} />
            <Toggle label="Show how I read your question" hint="Open under every answer; off folds it to one line" on={prefs.reading === "open"} set={(v) => setPrefs({ reading: v ? "open" : "folded" })} />
            <Toggle label="Open trends as a chart" hint="Answers by date or category start as a chart" on={prefs.chartFirst} set={(v) => setPrefs({ chartFirst: v })} />
            <Toggle label="Liquid Glass" hint="Off: solid surfaces, for less motion and more contrast" on={prefs.glass} set={(v) => setPrefs({ glass: v })} />
          </Group>

          <Group id="abilities" title={`What ${/^[aeiou]/i.test(ROLE[me.role]) ? "an" : "a"} ${ROLE[me.role].toLowerCase()} can do`}
                 footer={<Link className="more" to="/help">How to use ReBo<ArrowRight /></Link>}>
            {can.map((c) => <Row key={c} icon={Check} label={c} />)}
          </Group>

          <Group id="shortcuts" title="Keyboard shortcuts">
            <Row label="Search, ask or jump anywhere"><Keys k={["⌘", "K"]} /></Row>
            <Row label="Your conversations"><Keys k={["⌘", "/"]} /></Row>
            <Row label="Ask"><Keys k={["Enter"]} /></Row>
            <Row label="New line in a question"><Keys k={["Shift", "Enter"]} /></Row>
            <Row label="Help"><Keys k={["?"]} /></Row>
            <Row label="Close a sheet or dialog"><Keys k={["Esc"]} /></Row>
          </Group>

          <SignInAs />
          <p className="aboutlink"><Link to="/about">About ReBo<ArrowRight /></Link></p>
        </div>
      </div>
    </div>
  );
}

function Fig({ n, label, icon: Icon }: { n?: number; label: string; icon: LucideIcon }) {
  return <div className="fig"><dt><Icon />{label}</dt><dd>{n ?? "–"}</dd></div>;
}

// The sections as a floating glass rail; the one you are reading is lit.
function Rail() {
  const [at, setAt] = useState(SECTIONS[0].id);
  useEffect(() => {
    const io = new IntersectionObserver((es) => {
      const top = es.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setAt(top.target.id);
    }, { rootMargin: "-100px 0px -55% 0px" });
    SECTIONS.forEach((s) => { const el = document.getElementById(s.id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, []);
  return (
    <Glass as="nav" className="yourail" aria-label="Sections" strength={20}>
      {SECTIONS.map((s) => (
        <a key={s.id} href={`#${s.id}`} className={at === s.id ? "on" : undefined} aria-current={at === s.id ? "location" : undefined}><s.icon />{s.label}</a>
      ))}
    </Glass>
  );
}

function Group({ id, title, note, footer, children }: { id: string; title: string; note?: string; footer?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} className="group" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{title}</h2>
      {note && <p className="gnote">{note}</p>}
      <Glass className="glist" strength={22}>{children}</Glass>
      {footer && <div className="gfoot">{footer}</div>}
    </section>
  );
}

function Row({ label, icon: Icon, muted, children }: { label?: string; icon?: LucideIcon; muted?: boolean; children?: React.ReactNode }) {
  return (
    <div className={`grow-row${muted ? " muted" : ""}`}>
      {Icon && <span className="ricon"><Icon /></span>}
      <span className="rlabel">{label ?? children}</span>
      {label && children ? <span className="rend">{children}</span> : null}
    </div>
  );
}

function Seg({ label, value, set, options }: { label: string; value: string; set: (v: string) => void; options: [string, string][] }) {
  return (
    <ToggleButtonGroup aria-label={label} selectionMode="single" disallowEmptySelection className="segmented"
                       selectedKeys={[value]} onSelectionChange={(k) => set(String([...k][0]))}>
      {options.map(([k, l]) => <ToggleButton key={k} id={k}>{l}</ToggleButton>)}
    </ToggleButtonGroup>
  );
}

function Toggle({ label, hint, on, set }: { label: string; hint: string; on: boolean; set: (v: boolean) => void }) {
  return (
    <Switch className="grow-row switch" isSelected={on} onChange={set}>
      <span className="rlabel">{label}<small>{hint}</small></span>
      <span className="track" aria-hidden><span className="knob" /></span>
    </Switch>
  );
}

function Keys({ k }: { k: string[] }) {
  return <span className="keyset">{k.map((x, i) => <kbd key={i}>{x}</kbd>)}</span>;
}

function SignInAs() {
  const current = identity();
  const me = useMe();
  const demo = useDemo();
  const [user, setUser] = useState(displayName(current?.user ?? me?.id ?? "alice"));
  const [role, setRole] = useState<Identity["role"]>(current?.role ?? me?.role ?? "user");
  return (
    <Group id="sign-in" title="Signed in as" note="For trying ReBo on your own machine. Behind your company's sign-in this is decided there and has no effect.">
      <form className="grow-row signin" onSubmit={(e) => { e.preventDefault(); setIdentity({ user: personId(user.trim() || "alice", !!demo), role }); }}>
        <input className="input" aria-label="Name" value={user} onChange={(e) => setUser(e.target.value)} />
        <ToggleButtonGroup aria-label="Role" selectionMode="single" disallowEmptySelection className="segmented" selectedKeys={[role]}
                           onSelectionChange={(k) => setRole(String([...k][0]) as Identity["role"])}>
          <ToggleButton id="user">Member</ToggleButton><ToggleButton id="admin">Admin</ToggleButton><ToggleButton id="owner">Owner</ToggleButton>
        </ToggleButtonGroup>
        <button className="btn primary" type="submit">Switch</button>
      </form>
    </Group>
  );
}
