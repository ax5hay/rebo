// The bot's HTTP API (docs/10-api-and-ui.md). Identity: behind the login proxy the proxy adds it;
// for local use, ?user=<id>&role=<user|admin|owner> in the page URL is sent as X-User-* headers.
const params = new URLSearchParams(window.location.search);

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (params.get("user")) h["X-User-Id"] = params.get("user")!;
  if (params.get("role")) h["X-User-Role"] = params.get("role")!;
  return h;
}

export async function call<T = any>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api${path}`, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `${r.status}`);
  return data as T;
}

export type Step = { tool?: string; [k: string]: unknown };

// One turn over /api/agui: calls onStep for each tool step as it happens, resolves with the result.
export async function askStream(text: string, threadId: string, onStep: (s: Step) => void): Promise<any> {
  const body = {
    threadId, runId: crypto.randomUUID(), state: null, tools: [], context: [], forwardedProps: null,
    messages: [{ id: crypto.randomUUID(), role: "user", content: text }],
  };
  const r = await fetch("/api/agui", { method: "POST", headers: { ...headers(), Accept: "text/event-stream" },
                                       body: JSON.stringify(body) });
  if (!r.ok || !r.body) throw new Error((await r.json().catch(() => ({}))).detail || `${r.status}`);
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
      if (ev.type === "RUN_ERROR") throw new Error(ev.message);
    }
  }
  return result;
}
