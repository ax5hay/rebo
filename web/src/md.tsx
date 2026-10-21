// Every piece of text the bot, the model or a person writes is rendered as Markdown (GFM: lists, tables,
// code, links). Raw HTML is never rendered (react-markdown's default), links open in a new tab, and
// `inline` keeps a single paragraph inline so it can sit inside a sentence, a list item or a toast.
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const plugins = [remarkGfm];
const link: Components["a"] = ({ node: _, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />;
const block: Components = { a: link };
const inline: Components = { a: link, p: ({ children }) => <>{children}</> };

export function Md({ children, inline: isInline = false, className }: { children?: string | null; inline?: boolean; className?: string }) {
  if (!children) return null;
  const md = <Markdown remarkPlugins={plugins} components={isInline ? inline : block}>{children}</Markdown>;
  return isInline ? <span className={`md inline ${className ?? ""}`}>{md}</span> : <div className={`md ${className ?? ""}`}>{md}</div>;
}
