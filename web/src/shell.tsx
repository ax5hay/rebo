// The frame around every page: brand, sections for the person's role, who is signed in, and toasts.
import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";
import { get, identity, setIdentity, type Identity } from "./api";

export type Me = { id: string; role: "user" | "admin" | "owner"; team: string | null; is_admin: boolean; is_owner: boolean };

const ToastContext = createContext<(text: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);
const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext);

export default function Shell() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => get<Me>("/me"), retry: false });
  const [toast, setToast] = useState<string | null>(null);
  const say = useCallback((text: string) => setToast(text), []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4200);
    return () => clearTimeout(t);
  }, [toast]);

  if (me.isError) return <SignIn />;
  const m = me.data ?? null;
  return (
    <MeContext.Provider value={m}>
      <ToastContext.Provider value={say}>
        <header className="bar">
          <div className="brand">Re<b>Bo</b></div>
          <nav className="nav" aria-label="Sections">
            <NavLink to="/" end>Ask</NavLink>
            <NavLink to="/knowledge">What I taught</NavLink>
            {m?.is_admin && <NavLink to="/review">Review</NavLink>}
            {m?.is_admin && <NavLink to="/admin">Admin</NavLink>}
            {m?.is_admin && <NavLink to="/insights">Insights</NavLink>}
            {m?.is_owner && <NavLink to="/config">Configuration</NavLink>}
          </nav>
          <IdentityPicker me={m} />
        </header>
        <main>{m ? <Outlet /> : <p className="empty">Loading…</p>}</main>
        {toast && <div className="toast" role="status">{toast}</div>}
      </ToastContext.Provider>
    </MeContext.Provider>
  );
}

// Local and test use: pick who you are. Behind the login proxy the proxy decides and this is ignored.
function IdentityPicker({ me }: { me: Me | null }) {
  const current = identity();
  const [user, setUser] = useState(current?.user ?? me?.id ?? "alice");
  const [role, setRole] = useState<Identity["role"]>(current?.role ?? me?.role ?? "user");
  return (
    <form className="who" onSubmit={(e) => { e.preventDefault(); setIdentity({ user: user.trim() || "alice", role }); }}>
      <span>Signed in as</span>
      <input aria-label="User" value={user} onChange={(e) => setUser(e.target.value)} size={9} />
      <select aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as Identity["role"])}>
        <option value="user">user</option>
        <option value="admin">admin</option>
        <option value="owner">owner</option>
      </select>
      <button className="btn quiet" type="submit">Switch</button>
    </form>
  );
}

function SignIn() {
  const [user, setUser] = useState("alice");
  return (
    <main>
      <div className="starters">
        <h1>Who is asking?</h1>
        <p>ReBo answers as a person: what you teach it stays yours until it is shared. Behind your company's
          login this is filled in for you; here, give a name.</p>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setIdentity({ user, role: "user" }); }}>
          <input className="input" style={{ maxWidth: 260 }} aria-label="Your name" value={user} onChange={(e) => setUser(e.target.value)} />
          <button className="btn primary" type="submit">Continue</button>
        </form>
      </div>
    </main>
  );
}
