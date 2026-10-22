// ReBo's HTTP API (docs/10-api-and-ui.md). Identity: behind the login proxy the proxy adds it. For local
// use the page sends X-User-* from ?user=…&role=… or from the identity picker (kept in localStorage).

export type Identity = { user: string; role: "user" | "admin" | "owner" };

const KEY = "rebo.identity";

export function identity(): Identity | null {
  const q = new URLSearchParams(window.location.search);
  if (q.get("user")) {  // remembered, so moving between pages (which drops the query) keeps who you are
    const id: Identity = { user: q.get("user")!, role: (q.get("role") as Identity["role"]) || "user" };
    try { localStorage.setItem(KEY, JSON.stringify(id)); } catch { /* private mode */ }
    return id;
  }
  try {
    const saved = localStorage.getItem(KEY);
    return saved ? (JSON.parse(saved) as Identity) : null;
  } catch {
    return null;
  }
}

export function setIdentity(id: Identity) {
  try {
    localStorage.setItem(KEY, JSON.stringify(id));
  } catch {
    /* private mode: the URL still works */
  }
  const url = new URL(window.location.href);
  url.searchParams.delete("user");
  url.searchParams.delete("role");
  window.location.assign(url.toString());
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const id = identity();
  if (id) {
    h["X-User-Id"] = id.user;
    h["X-User-Role"] = id.role;
  }
  return h;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function call<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api${path}`, { method, headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await r.text();
  let data: any = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = text;
  }
  if (!r.ok) throw new ApiError(r.status, (data && data.detail) || `${r.status}`);
  return data as T;
}

export const get = <T = any>(path: string) => call<T>("GET", path);

export async function getText(path: string): Promise<string> {
  const r = await fetch(`/api${path}`, { headers: headers() });
  if (!r.ok) throw new ApiError(r.status, `${r.status}`);
  return r.text();
}

export function csvUrl(turnId: string) {
  const id = identity();
  const q = id ? `?user=${encodeURIComponent(id.user)}&role=${id.role}` : "";
  return `/api/turns/${turnId}/csv${q}`;
}

export type Step = { tool?: string; say?: string; [k: string]: unknown };

// One question over /api/agui: onStep sees each tool step as it happens; resolves with the answer.
export async function askStream(text: string, threadId: string, onStep: (s: Step) => void): Promise<any> {
  const body = {
    threadId, runId: crypto.randomUUID(), state: null, tools: [], context: [], forwardedProps: null,
    messages: [{ id: crypto.randomUUID(), role: "user", content: text }],
  };
  const r = await fetch("/api/agui", { method: "POST", headers: { ...headers(), Accept: "text/event-stream" },
                                       body: JSON.stringify(body) });
  if (!r.ok || !r.body) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail || `${r.status}`);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: any = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.type === "CUSTOM" && ev.name === "rebo.progress") onStep(ev.value);
      if (ev.type === "CUSTOM" && ev.name === "rebo.result") result = ev.value;
      if (ev.type === "RUN_ERROR") throw new ApiError(500, ev.message);
    }
  }
  return result;
}

export function when(ts?: number | null) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  const dateOnly = d.getHours() === 0 && d.getMinutes() === 0 && d.getSeconds() === 0;  // runs recorded by date
  return d.toLocaleString(undefined, dateOnly ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" });
}

export const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;


// Public demo: a name is not a secret, so two visitors who type the same name must not become one
// person. Each browser keeps a short random tag, added to the id as "name#tag" (yours stays the same,
// so you return to your own sessions in this browser). Shown everywhere without the tag.
const TAG_KEY = "rebo.tag";

export function personId(name: string, publicDemo: boolean): string {
  const base = name.trim().split("#")[0];
  if (!publicDemo) return base;
  let tag = "";
  try {
    tag = localStorage.getItem(TAG_KEY) || "";
    if (!tag) {
      tag = Math.random().toString(36).slice(2, 7);
      localStorage.setItem(TAG_KEY, tag);
    }
  } catch { /* private mode: a fresh tag each time, still never someone else's */ tag = Math.random().toString(36).slice(2, 7); }
  return `${base}#${tag}`;
}

export const displayName = (id: string | null | undefined) => (id ?? "").split("#")[0];
