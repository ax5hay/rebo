// A chart only when the result is a measured comparison: one label or date per row (each appearing
// once) and one to three real measures, 2 to 60 rows. Identifiers are never measures and never bar
// labels (a bar per case id says nothing), and a plain list of records, a query with no aggregate, gets
// a chart only along a date. Dates become a line, labels become bars in the table's order. One measure
// at a time, with a picker when there are several. Observable Plot, loaded only when someone opens the
// chart. The table stays the default.
import { useEffect, useRef, useState } from "react";

const DATE = /^\d{4}(-\d{2}(-\d{2})?([ T].*)?)?$/;
// case_id, caseId, CaseID, contact id, ref, phone, zip ... (snake, camel and spaced names)
export const IDENTIFIER = /(^|[_\s-])(id|ids|key|code|number|num|no|nr|ref|uuid|guid|phone|mobile|zip|postcode|pin)$|[a-z0-9](Id|ID|Ids|Key|Code|Number|Num|No|Nr|Ref|Uuid)$|^(id|key|pk|uuid)$/i;
const YEAR = /(^|[_\s-])(year|yr)$|[a-z]Year$|^year$/i;
const AGGREGATE = /\b(group\s+by|count|sum|avg|min|max|median|percentile\w*|stddev\w*)\s*\(|\bgroup\s+by\b/i;

export function chartShape(columns: string[], rows: any[][], sql?: string): { x: number; ys: number[]; dates: boolean } | null {
  if (rows.length < 2 || rows.length > 60 || columns.length < 2) return null;
  const numeric = columns.map((_, c) => rows.every((r) => r[c] === null || typeof r[c] === "number"));
  const isDate = (c: number) => rows.every((r) => r[c] !== null && DATE.test(String(r[c])) && (typeof r[c] === "string" || YEAR.test(columns[c])));
  const unique = (c: number) => new Set(rows.map((r) => String(r[c]))).size === rows.length;
  const id = (c: number) => IDENTIFIER.test(columns[c].trim());
  // x: a date (or year) column first, else the first text column that is not an identifier
  let x = columns.findIndex((_, c) => isDate(c) && unique(c));
  const dates = x >= 0;
  if (!dates) x = numeric.findIndex((n, c) => !n && !id(c));
  if (x < 0 || !unique(x)) return null;                       // repeated labels: a list of records
  if (!dates && sql && !AGGREGATE.test(sql)) return null;     // records, not a measured comparison
  const ys = numeric.flatMap((n, i) => (n && i !== x && !id(i) && !YEAR.test(columns[i]) ? [i] : [])).slice(0, 3);
  if (ys.length === 0 || ys.every((c) => rows.every((r) => r[c] === rows[0][c]))) return null;  // nothing varies
  return { x, ys, dates };
}

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export default function ResultChart({ columns, rows, sql }: { columns: string[]; rows: any[][]; sql?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const shape = chartShape(columns, rows, sql)!;
  const [y, setY] = useState(shape.ys[0]);
  const label = (c: number) => columns[c].replaceAll("_", " ");
  useEffect(() => {
    let el: Element | null = null;
    import("@observablehq/plot").then((Plot) => {
      if (!ref.current) return;
      const data = rows.map((r) => ({ x: shape.dates ? new Date(/^\d{4}$/.test(String(r[shape.x])) ? `${r[shape.x]}-01-01` : String(r[shape.x])) : String(r[shape.x]), y: r[y] }));
      const ink = css("--accent");
      const width = Math.max(ref.current.clientWidth - 8, 320);
      el = Plot.plot({
        width, height: 300, marginLeft: 56, marginBottom: shape.dates ? 32 : 64,
        style: { background: "transparent", fontSize: "12px", color: css("--ink-2"), fontFamily: "var(--font)" },
        y: { grid: true, label: label(y) },
        x: shape.dates ? { label: null } : { label: null, domain: rows.map((r) => String(r[shape.x])), tickRotate: rows.length > 8 ? -35 : 0 },
        marks: shape.dates
          ? [Plot.lineY(data, { x: "x", y: "y", stroke: ink, strokeWidth: 2, sort: "x" }), Plot.dot(data, { x: "x", y: "y", fill: ink, r: 3, tip: true }), Plot.ruleY([0], { stroke: css("--line-2") })]
          : [Plot.barY(data, { x: "x", y: "y", fill: ink, tip: true, inset: 4 }), Plot.ruleY([0], { stroke: css("--line-2") })],
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
