// A chart for results that suit one: a label or date column and one to three numeric columns, at most
// 60 rows. Dates become a line, labels become bars in the table's order. One measure at a time (measures
// on different scales flatten each other), with a picker when there are several. Observable Plot, loaded
// only when someone opens the chart. The table stays the default.
import { useEffect, useRef, useState } from "react";

const DATE = /^\d{4}-\d{2}(-\d{2})?([ T].*)?$/;

export function chartShape(columns: string[], rows: any[][]): { x: number; ys: number[]; dates: boolean } | null {
  if (rows.length < 2 || rows.length > 60 || columns.length < 2) return null;
  const numeric = columns.map((_, c) => rows.every((r) => r[c] === null || typeof r[c] === "number"));
  const x = numeric.findIndex((n) => !n);
  const ys = numeric.flatMap((n, i) => (n && i !== x ? [i] : [])).slice(0, 3);
  if (x < 0 || ys.length === 0) return null;
  return { x, ys, dates: rows.every((r) => r[x] !== null && DATE.test(String(r[x]))) };
}

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export default function ResultChart({ columns, rows }: { columns: string[]; rows: any[][] }) {
  const ref = useRef<HTMLDivElement>(null);
  const shape = chartShape(columns, rows)!;
  const [y, setY] = useState(shape.ys[0]);
  const label = (c: number) => columns[c].replaceAll("_", " ");
  useEffect(() => {
    let el: Element | null = null;
    import("@observablehq/plot").then((Plot) => {
      if (!ref.current) return;
      const data = rows.map((r) => ({ x: shape.dates ? new Date(String(r[shape.x])) : String(r[shape.x]), y: r[y] }));
      const ink = css("--accent");
      const width = Math.max(ref.current.clientWidth - 8, 320);
      el = Plot.plot({
        width, height: 300, marginLeft: 56, marginBottom: shape.dates ? 32 : 64,
        style: { background: "transparent", fontSize: "12px", color: css("--text-2"), fontFamily: "var(--font)" },
        y: { grid: true, label: label(y) },
        x: shape.dates ? { label: null } : { label: null, domain: rows.map((r) => String(r[shape.x])), tickRotate: rows.length > 8 ? -35 : 0 },
        marks: shape.dates
          ? [Plot.lineY(data, { x: "x", y: "y", stroke: ink, strokeWidth: 2, sort: "x" }), Plot.dot(data, { x: "x", y: "y", fill: ink, r: 3, tip: true }), Plot.ruleY([0], { stroke: css("--border-strong") })]
          : [Plot.barY(data, { x: "x", y: "y", fill: ink, tip: true, inset: 4 }), Plot.ruleY([0], { stroke: css("--border-strong") })],
      });
      ref.current.replaceChildren(el);
    });
    return () => el?.remove();
  }, [columns, rows, y]);
  return (
    <div className="result-chart">
      {shape.ys.length > 1 && (
        <div className="row measures" role="group" aria-label="Measure">
          {shape.ys.map((c) => <button key={c} className="chip" aria-pressed={c === y} onClick={() => setY(c)}>{label(c)}</button>)}
        </div>
      )}
      <div className="chart" ref={ref} role="img" aria-label={`${label(y)} by ${label(shape.x)}`} />
    </div>
  );
}
