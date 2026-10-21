// The frame around every page: sidebar (sections, recent conversations, who is signed in), the page
// title bar, toasts, and the command palette (⌘K / Ctrl+K).
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import {
  Activity, BookMarked, ClipboardCheck, Command as CommandIcon, MessageSquarePlus, MessagesSquare, Menu as MenuIcon,
  Search, Settings2, Shield,
} from "lucide-react";
import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { toast, Toaster } from "sonner";
import { get, identity, setIdentity, type Identity } from "./api";

export type Me = { id: string; role: "user" | "admin" | "owner"; team: string | null; is_admin: boolean; is_owner: boolean };

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext);
export const useToast = () => (text: string) => toast(text);
const PaletteContext = createContext<(open: boolean) => void>(() => {});
export const usePalette = () => useContext(PaletteContext);

const PAGES = [
  { to: "/", label: "Ask", icon: MessagesSquare, end: true },
  { to: "/knowledge", label: "What I taught", icon: BookMarked },
  { to: "/review", label: "Review", icon: ClipboardCheck, admin: true },
  { to: "/admin", label: "Admin", icon: Shield, admin: true },
  { to: "/insights", label: "Insights", icon: Activity, admin: true },
  { to: "/config", label: "Configuration", icon: Settings2, owner: true },
];
const TITLES: Record<string, string> = { "": "Ask", knowledge: "What I taught", review: "Review", admin: "Admin",
                                        insights: "Insights", config: "Configuration", c: "Conversation" };

export default function Shell() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => get<Me>("/me"), retry: false });
  const [palette, setPalette] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
    };
    const onScroll = () => setScrolled(window.scrollY > 4);
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("scroll", onScroll); };
  }, []);
  useEffect(() => setDrawer(false), [location.pathname]);

  if (me.isError) return <SignIn />;
  const m = me.data ?? null;
  const title = TITLES[location.pathname.split("/")[1] ?? ""] ?? "ReBo";
  return (
    <MeContext.Provider value={m}>
      <PaletteContext.Provider value={setPalette}>
        <div className="app">
          <Sidebar me={m} open={drawer} openPalette={() => setPalette(true)} />
          <div className="main">
            <header className={`topbar${scrolled ? " scrolled" : ""}`}>
              <button className="btn ghost icon menubtn" aria-label="Open navigation" onClick={() => setDrawer((d) => !d)}><MenuIcon /></button>
              <h1>{title}</h1>
              <span className="spacer" />
              <button className="btn ghost" onClick={() => setPalette(true)}><Search /> Search or ask <kbd>⌘K</kbd></button>
            </header>
            <div className="content">{m ? <Outlet /> : <p className="empty">Loading…</p>}</div>
          </div>
        </div>
        {palette && m && <Palette me={m} close={() => setPalette(false)} />}
        <Toaster position="bottom-right" toastOptions={{ style: { fontFamily: "var(--font)", borderRadius: 10 } }} />
      </PaletteContext.Provider>
    </MeContext.Provider>
  );
}

function Sidebar({ me, open, openPalette }: { me: Me | null; open: boolean; openPalette: () => void }) {
  const navigate = useNavigate();
  const recent = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations"), enabled: !!me });
  return (
    <aside className={`sidebar${open ? " open" : ""}`} aria-label="Navigation">
      <div className="brand">
        <span className="mark" aria-hidden>Rb</span><span className="name">ReBo</span>
        <button className="btn ghost icon" aria-label="Command palette" onClick={openPalette} style={{ marginLeft: "auto" }}><CommandIcon /></button>
      </div>
      <button className="btn newq" onClick={() => navigate("/")}><MessageSquarePlus /> New question</button>
      <nav className="navgroup" aria-label="Sections">
        {PAGES.filter((p) => (!p.admin || me?.is_admin) && (!p.owner || me?.is_owner)).map((p) => (
          <NavLink key={p.to} to={p.to} end={p.end} className={({ isActive }) => `navitem${isActive ? " active" : ""}`}>
            <p.icon />{p.label}
          </NavLink>
        ))}
      </nav>
      {(recent.data?.length ?? 0) > 0 && (
        <nav className="navgroup" aria-label="Recent conversations">
          <span className="label">Recent</span>
          {recent.data!.slice(0, 12).map((c) => (
            <NavLink key={c.id} to={`/c/${c.id}`} className={({ isActive }) => `navitem recent${isActive ? " active" : ""}`} title={c.title}>
              <span>{c.title}</span>
            </NavLink>
          ))}
        </nav>
      )}
      <div className="footer"><Who me={me} /></div>
    </aside>
  );
}

// Who is signed in. Behind the login proxy that is decided there; locally you can switch here.
function Who({ me }: { me: Me | null }) {
  const current = identity();
  const [user, setUser] = useState(current?.user ?? me?.id ?? "alice");
  const [role, setRole] = useState<Identity["role"]>(current?.role ?? me?.role ?? "user");
  return (
    <>
      <div className="whoami">
        <span className="avatar">{(me?.id ?? "?").slice(0, 1)}</span>
        <span className="meta"><b>{me?.id}</b><span>{me?.role === "owner" ? "Owner" : me?.role === "admin" ? "Admin" : "Member"}</span></span>
      </div>
      <form className="devpick" onSubmit={(e) => { e.preventDefault(); setIdentity({ user: user.trim() || "alice", role }); }}>
        <input className="input" aria-label="Switch user" value={user} onChange={(e) => setUser(e.target.value)} />
        <select className="select" aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as Identity["role"])}>
          <option value="user">Member</option><option value="admin">Admin</option><option value="owner">Owner</option>
        </select>
        <button className="btn" type="submit">Switch</button>
      </form>
    </>
  );
}

function Palette({ me, close }: { me: Me; close: () => void }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const recent = useQuery({ queryKey: ["conversations"], queryFn: () => get<any[]>("/conversations") });
  const go = (to: string) => { navigate(to); close(); };
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <Command label="Command palette" onKeyDown={(e) => e.key === "Escape" && close()}>
        <Command.Input autoFocus value={q} onValueChange={setQ} placeholder="Ask a question or jump to…" />
        <Command.List>
          <Command.Empty>Press Enter to ask this.</Command.Empty>
          {q.trim() && (
            <Command.Group heading="Ask">
              <Command.Item value={`ask ${q}`} onSelect={() => go(`/?q=${encodeURIComponent(q)}`)}><MessagesSquare />Ask “{q}”</Command.Item>
            </Command.Group>
          )}
          <Command.Group heading="Go to">
            {PAGES.filter((p) => (!p.admin || me.is_admin) && (!p.owner || me.is_owner)).map((p) => (
              <Command.Item key={p.to} value={`go ${p.label}`} onSelect={() => go(p.to)}><p.icon />{p.label}</Command.Item>
            ))}
          </Command.Group>
          {(recent.data?.length ?? 0) > 0 && (
            <Command.Group heading="Recent conversations">
              {recent.data!.slice(0, 8).map((c) => (
                <Command.Item key={c.id} value={`recent ${c.title} ${c.id}`} onSelect={() => go(`/c/${c.id}`)}><MessagesSquare />{c.title}</Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  );
}

function SignIn() {
  const [user, setUser] = useState("alice");
  return (
    <div className="content" style={{ maxWidth: 520 }}>
      <div className="hello">
        <span className="brand" style={{ padding: 0, marginBottom: 18 }}><span className="mark">Rb</span><span className="name">ReBo</span></span>
        <h1>Who is asking?</h1>
        <p>ReBo answers as a person: what you teach it stays yours until it is shared. Behind your company's
          sign-in this is filled in for you; here, give a name.</p>
        <form className="row" style={{ marginTop: 18 }} onSubmit={(e) => { e.preventDefault(); setIdentity({ user, role: "user" }); }}>
          <input className="input" style={{ maxWidth: 260 }} aria-label="Your name" value={user} onChange={(e) => setUser(e.target.value)} />
          <button className="btn primary" type="submit">Continue</button>
        </form>
      </div>
    </div>
  );
}
