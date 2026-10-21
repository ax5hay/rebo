// Personal display preferences, kept in this browser (the "You" page edits them). They change how
// things look, never what ReBo answers, so they do not belong on the server.
import { useSyncExternalStore } from "react";

export type Prefs = {
  theme: "auto" | "light" | "dark";
  density: "comfortable" | "compact";
  stripes: boolean;          // alternate row tint in result tables
  reading: "open" | "folded"; // "How I read your question" open by default
  chartFirst: boolean;       // open chart-shaped answers as a chart
  glass: boolean;            // Liquid Glass on the navigation layer (off = solid surfaces)
};

const KEY = "rebo.prefs";
const DEFAULTS: Prefs = { theme: "auto", density: "comfortable", stripes: true, reading: "open", chartFirst: false, glass: true };
const listeners = new Set<() => void>();
let current: Prefs = load();

function load(): Prefs {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") }; } catch { return DEFAULTS; }
}

export function applyPrefs(p: Prefs = current) {
  const root = document.documentElement;
  if (p.theme === "auto") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", p.theme);
  root.dataset.density = p.density;
  root.dataset.stripes = String(p.stripes);
  root.dataset.glass = String(p.glass);
}

export function setPrefs(patch: Partial<Prefs>) {
  current = { ...current, ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(current)); } catch { /* private mode: this visit only */ }
  applyPrefs();
  listeners.forEach((l) => l());
}

export function usePrefs(): Prefs {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => current);
}
