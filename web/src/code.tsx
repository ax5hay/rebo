// Code surfaces: an editor for the configuration and the knowledge file (YAML) and for queries (SQL),
// and highlighted read-only queries. CodeMirror 6 (MIT) and its Lezer parsers, loaded on first use so
// the Ask page stays light. Colours come from the theme tokens (.tok-* and .cm-* in styles.css).
import { useEffect, useRef, useState, type ReactNode } from "react";

type Lang = "yaml" | "sql";

async function editorParts(lang: Lang) {
  const [view, state, language, commands, highlight, mode] = await Promise.all([
    import("@codemirror/view"), import("@codemirror/state"), import("@codemirror/language"), import("@codemirror/commands"),
    import("@lezer/highlight"),
    lang === "yaml" ? import("@codemirror/lang-yaml").then((m) => m.yaml()) : import("@codemirror/lang-sql").then((m) => m.sql()),
  ]);
  return { ...view, ...state, ...language, ...commands, ...highlight, mode };
}

export function CodeEditor({ value, onChange, lang, label, rows = 16, wrap = lang === "sql" }: {
  value: string; onChange: (v: string) => void; lang: Lang; label: string; rows?: number; wrap?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<any>(null);
  const latest = useRef({ value, onChange });
  latest.current = { value, onChange };

  useEffect(() => {
    let dead = false;
    editorParts(lang).then((p) => {
      if (dead || !host.current) return;
      view.current = new p.EditorView({
        parent: host.current,
        state: p.EditorState.create({
          doc: latest.current.value,
          extensions: [
            p.lineNumbers(), p.history(), p.drawSelection(), p.highlightActiveLine(), p.indentOnInput(), p.bracketMatching(),
            p.syntaxHighlighting(p.classHighlighter), p.keymap.of([...p.defaultKeymap, ...p.historyKeymap, p.indentWithTab]),
            p.mode, ...(wrap ? [p.EditorView.lineWrapping] : []), p.EditorView.contentAttributes.of({ "aria-label": label }),
            p.EditorView.updateListener.of((u: any) => { if (u.docChanged) latest.current.onChange(u.state.doc.toString()); }),
          ],
        }),
      });
    });
    return () => { dead = true; view.current?.destroy(); view.current = null; };
  }, [lang, label, wrap]);

  // a new value from outside (loaded, reset, restored) replaces the document
  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
  }, [value]);

  return <div className="cm-host" ref={host} style={{ minHeight: rows * 20 }} />;
}

export function SqlCode({ sql }: { sql: string }) {
  const [parts, setParts] = useState<ReactNode[] | null>(null);
  useEffect(() => {
    let dead = false;
    Promise.all([import("@codemirror/lang-sql"), import("@lezer/highlight")]).then(([{ StandardSQL }, { highlightCode, classHighlighter }]) => {
      const out: ReactNode[] = [];
      highlightCode(sql, StandardSQL.language.parser.parse(sql), classHighlighter,
        (text, cls) => out.push(cls ? <span key={out.length} className={cls}>{text}</span> : text), () => out.push("\n"));
      if (!dead) setParts(out);
    });
    return () => { dead = true; };
  }, [sql]);
  return <pre className="code sql">{parts ?? sql}</pre>;
}
