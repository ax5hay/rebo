// What a public demo limits, and why, from /api/health (`demo` is null on a normal install, where nothing
// here shows). The data sentence comes from the deployment's demo_note; the scale from the catalog.
import { useQuery } from "@tanstack/react-query";
import { Database, Gauge, Lock, Sparkles } from "lucide-react";
import { Link } from "react-router";

export type Demo = { owner_locked: boolean; daily_allowance: boolean; paced: boolean; note: string | null; tables: number | null; rows: number | null };

export function useDemo(): Demo | null {
  const q = useQuery({ queryKey: ["health"], staleTime: 5 * 60_000,
                       queryFn: () => fetch("/api/health").then((r) => r.json()) as Promise<{ demo: Demo | null }> });
  return q.data?.demo ?? null;
}

const rough = (n: number) => (n >= 1e6 ? `about ${(n / 1e6).toFixed(1)} million` : n >= 1e3 ? `about ${Math.round(n / 1e3)} thousand` : String(n));

export function scale(d: Demo): string | null {
  return d.tables ? `${d.tables} tables${d.rows ? ` and ${rough(d.rows)} rows` : ""}` : null;
}

// The limits as short lines: what, and the reason in a few words.
export function limits(d: Demo): { icon: typeof Lock; text: string }[] {
  const out = [];
  if (d.owner_locked) out.push({ icon: Lock, text: "Owner is locked: it changes the site for every visitor" });
  if (d.daily_allowance) out.push({ icon: Gauge, text: "New questions have a daily allowance, so the demo stays open to everyone" });
  if (d.paced) out.push({ icon: Gauge, text: "A few questions a minute per visitor" });
  return out;
}

/** A compact notice: the data, then what is limited. `variant` places it on the welcome card or in a page. */
export function DemoNotice({ demo, variant = "page" }: { demo: Demo; variant?: "welcome" | "page" }) {
  const size = scale(demo);
  return (
    <aside className={`demonotice on-${variant}`} aria-label="About this public demo">
      <p className="dhead"><Sparkles />Public demo</p>
      <p className="ddata"><Database />{demo.note ?? "This is a public demo."}{size ? ` ${size}.` : ""}</p>
      <ul>{limits(demo).map((l) => <li key={l.text}><l.icon />{l.text}</li>)}</ul>
      <p className="dfree">Saved reports, re-runs and the Read as switches are always free. {variant === "page" && <Link to="/about#demo">More</Link>}</p>
    </aside>
  );
}
