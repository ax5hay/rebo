// The frame around every page. No sidebar: a floating glass bar of three islands (brand and history;
// sections, with a lens that slides to the open one; tools and you), content scrolling underneath, the
// conversation history in a glass sheet, and on phones a floating tab bar at the bottom. ⌘K opens the
// command palette, ⌘/ the history, ? the help page.
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import {
  Activity, BookMarked, CircleHelp, ClipboardCheck, History, Info, MessagesSquare, Plus, Search, Settings2, Shield, SquarePen, SunMoon, UserRound, X,
} from "lucide-react";
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { toast, Toaster } from "sonner";
import { displayName, get, setIdentity, when } from "./api";
import { Mark, Wordmark } from "./brand";
import { Glass } from "./glass";
import { Welcome } from "./welcome";
import { Md } from "./md";
import { applyPrefs, getPrefs, setPrefs } from "./prefs";

export type Me = { id: string; role: "user" | "admin" | "owner"; team: string | null; is_admin: boolean; is_owner: boolean };

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext);
export const useToast = () => (text: string) => toast(<Md inline>{text}</Md>);
const PaletteContext = createContext<(open: boolean) => void>(() => {});
export const usePalette = () => useContext(PaletteContext);

export const PAGES = [
  { to: "/", label: "Ask", icon: MessagesSquare, end: true },
  { to: "/knowledge", label: "Knowledge", icon: BookMarked },
  { to: "/review", label: "Review", icon: ClipboardCheck, admin: true },
  { to: "/admin", label: "Admin", icon: Shield, admin: true },
  { to: "/insights", label: "Insights", icon: Activity, admin: true },
  { to: "/config", label: "Configuration", icon: Settings2, owner: true },
];
const visible = (me: Me | null) => PAGES.filter((p) => (!p.admin || me?.is_admin) && (!p.owner || me?.is_owner));
export const ROLE = { user: "Member", admin: "Admin", owner: "Owner" } as const;

export default function Shell() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => get<Me>("/me"), retry: false });
  const [palette, setPalette] = useState(false);
  const [history, setHistory] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => { applyPrefs(); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
      else if ((e.metaKey || e.ctrlKey) && e.key === "/") { e.preventDefault(); setHistory((h) => !h); }
      else if (!typing && e.key === "?") navigate("/help");
      else if (e.key === "Escape") setHistory(false);
    };
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("scroll", onScroll); };
  }, [navigate]);
  useEffect(() => setHistory(false), [location.pathname]);

  if (me.isError) return <Welcome />;
  const m = me.data ?? null;
  return (
    <MeContext.Provider value={m}>
      <PaletteContext.Provider value={setPalette}>
        <div className={`frame${scrolled ? " scrolled" : ""}`}>
          <header className="bar">
            <Glass className="island brandisland">
              <button className="iconbtn" aria-label="Conversations (⌘/)" title="Conversations (⌘/)" onClick={() => setHistory(true)}><History /></button>
              <Link to="/" className="home" aria-label="ReBo, new question"><Wordmark size={26} /></Link>
            </Glass>
            <Tabs me={m} />
            <Glass className="island tools">
              <button className="iconbtn" aria-label="New question" title="New question" onClick={() => navigate("/")}><SquarePen /></button>
              <button className="iconbtn wide" aria-label="Search or ask (⌘K)" onClick={() => setPalette(true)}><Search /><span className="kbdhint">⌘K</span></button>
              <NavLink to="/help" className={({ isActive }) => `iconbtn${isActive ? " on" : ""}`} aria-label="Help (?)" title="Help (?)"><CircleHelp /></NavLink>
              <Glass as={NavLink} to="/about" className="aboutpill" strength={18} aria-label="About ReBo" title="About ReBo"><Info /><span>About</span></Glass>
              <NavLink to="/me" className={({ isActive }) => `me${isActive ? " on" : ""}`} aria-label={`You: ${displayName(m?.id)}`} title="You: settings, reports, sign-in">
                <span className="avatar">{(m?.id ?? "?").slice(0, 1)}</span>
              </NavLink>
            </Glass>
          </header>
          <main className="content">{m ? <Outlet /> : <p className="empty">Loading…</p>}</main>
          <PhoneTabs openHistory={() => setHistory(true)} />
        </div>
        {history && m && <HistorySheet close={() => setHistory(false)} />}
        {palette && m && <Palette me={m} close={() => setPalette(false)} openHistory={() => setHistory(true)} />}
        <Toaster position="top-center" offset={78} toastOptions={{ className: "toast" }} />
      </PaletteContext.Provider>
    </MeContext.Provider>
  );
}

// Section tabs; a lens slides to the open one with a spring, like a drop moving under a finger.
function Tabs({ me }: { me: Me | null }) {
  const track = useRef<HTMLSpanElement>(null);
  const location = useLocation();
  const [lens, setLens] = useState<{ x: number; w: number } | null>(null);
  const pages = visible(me);
  useLayoutEffect(() => {
    const measure = () => {
      const a = track.current?.querySelector<HTMLElement>("a.on");
      setLens(a ? { x: a.offsetLeft, w: a.offsetWidth } : null);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [location.pathname, pages.length]);
  if (pages.length < 2) return <span className="tabs-spacer" />;
  return (
    <Glass as="nav" className="island tabs" aria-label="Sections">
      <span className="tabtrack" ref={track}>
        {lens && <span className="lens" style={{ transform: `translateX(${lens.x}px)`, width: lens.w }} aria-hidden />}
        {pages.map((p) => (
          <NavLink key={p.to} to={p.to} end={p.end} className={({ isActive }) => (isActive || (p.to === "/" && location.pathname.startsWith("/c/")) ? "on" : "")}>
            <p.icon />{p.label}
          </NavLink>
        ))}
      </span>
    </Glass>
  );
}

function PhoneTabs({ openHistory }: { openHistory: () => void }) {
  const cls = ({ isActive }: { isActive: boolean }) => (isActive ? "on" : "");
  return (
    <Glass as="nav" className="phonetabs" aria-label="Sections on a phone">
      <NavLink to="/" end className={cls}><MessagesSquare /><span>Ask</span></NavLink>
      <NavLink to="/knowledge" className={cls}><BookMarked /><span>Knowledge</span></NavLink>
      <button onClick={openHistory}><History /><span>History</span></button>
      <NavLink to="/help" className={cls}><CircleHelp /><span>Help</span></NavLink>
      <NavLink to="/me" className={cls}><UserRound /><span>You</span></NavLink>
    </Glass>
  );
}

function HistorySheet({ close }: { close: () => void }) {
  const recent = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations") });
  const [q, setQ] = useState("");
  const rows = (recent.data ?? []).filter((c) => c.title.toLowerCase().includes(q.trim().toLowerCase()));
  const today = new Date().toDateString();
  const isToday = (c: any) => new Date(c.updated_at * 1000).toDateString() === today;
  const groups: [string, any[]][] = [["Today", rows.filter(isToday)], ["Earlier", rows.filter((c) => !isToday(c))]];
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <Glass as="aside" className="sheet" aria-label="Conversations" strength={18}>
        <div className="sheethead">
          <h2>Conversations</h2>
          <button className="iconbtn" aria-label="Close" onClick={close}><X /></button>
        </div>
        <input className="input" autoFocus placeholder="Find a conversation" aria-label="Find a conversation" value={q} onChange={(e) => setQ(e.target.value)} />
        <Link to="/" className="btn primary block" onClick={close}><SquarePen />New question</Link>
        <div className="sheetlist">
          {groups.map(([label, items]) => items.length > 0 && (
            <section key={label}>
              <h3>{label}</h3>
              {items.map((c) => (
                <NavLink key={c.id} to={`/c/${c.id}`} className={({ isActive }) => `conv${isActive ? " on" : ""}`}>
                  <span className="t">{c.title}</span><span className="w">{when(c.updated_at)}</span>
                </NavLink>
              ))}
            </section>
          ))}
          {rows.length === 0 && <p className="empty">{q ? "No conversation matches." : "Your conversations appear here."}</p>}
        </div>
      </Glass>
    </div>
  );
}

function Palette({ me, close, openHistory }: { me: Me; close: () => void; openHistory: () => void }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const recent = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations") });
  const go = (to: string) => { navigate(to); close(); };
  const places = [...visible(me), { to: "/me", label: "You and your settings", icon: UserRound }, { to: "/help", label: "Help", icon: CircleHelp }, { to: "/about", label: "About ReBo", icon: Info }];
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <Glass className="palette" strength={30}>
      <Command label="Command palette" onKeyDown={(e) => e.key === "Escape" && close()}>
        <Command.Input autoFocus value={q} onValueChange={setQ} placeholder="Ask a question or jump to…" />
        <Command.List>
          <Command.Empty>Press Enter to ask this.</Command.Empty>
          {q.trim() && (
            <Command.Group heading="Ask">
              <Command.Item value={`ask ${q}`} onSelect={() => go(`/?q=${encodeURIComponent(q)}`)}><MessagesSquare />Ask “{q}”</Command.Item>
            </Command.Group>
          )}
          <Command.Group heading="Actions">
            <Command.Item value="action new question" onSelect={() => go("/")}><SquarePen />New question</Command.Item>
            <Command.Item value="action teach something new knowledge" onSelect={() => go("/knowledge?teach=1")}><Plus />Teach ReBo something</Command.Item>
            <Command.Item value="action appearance dark light theme" onSelect={() => { const p = getPrefs(); setPrefs({ theme: p.theme === "dark" ? "light" : p.theme === "light" ? "auto" : "dark" }); close(); }}><SunMoon />Change appearance (auto, dark, light)</Command.Item>
            <Command.Item value="action history conversations" onSelect={() => { close(); openHistory(); }}><History />Your conversations</Command.Item>
          </Command.Group>
          <Command.Group heading="Go to">
            {places.map((p) => <Command.Item key={p.to} value={`go ${p.label}`} onSelect={() => go(p.to)}><p.icon />{p.label}</Command.Item>)}
          </Command.Group>
          {(recent.data?.length ?? 0) > 0 && (
            <Command.Group heading="Recent conversations">
              {recent.data!.slice(0, 8).map((c) => (
                <Command.Item key={c.id} value={`recent ${c.title} ${c.id}`} onSelect={() => go(`/c/${c.id}`)}><History />{c.title}</Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
      </Glass>
    </div>
  );
}

