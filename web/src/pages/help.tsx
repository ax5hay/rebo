// How to use ReBo, in short scannable sections. Every feature links to where it lives, and example
// questions run with one click ("Try it"). Admin and owner sections show only to those roles.
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight, BadgeCheck, BookMarked, CircleAlert, Download, Eye, Hand, Keyboard, Lightbulb, ListChecks, MessageSquareText,
  MousePointerClick, Pin, RotateCcw, ShieldCheck, Sparkles, Timer, Undo2, Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { get } from "../api";
import { Glass } from "../glass";
import { useMe } from "../shell";
import { PageHead } from "../ui";

type Section = { id: string; title: string; icon: any; admin?: boolean; owner?: boolean; body: React.ReactNode };

const Try = ({ q }: { q: string }) => <Link className="try" to={`/?q=${encodeURIComponent(q)}`}><Sparkles />{q}</Link>;
const Go = ({ to, children }: { to: string; children: React.ReactNode }) => <Link className="go" to={to}>{children}<ArrowRight /></Link>;

export default function HelpPage() {
  const me = useMe();
  const { hash } = useLocation();
  const starters = useQuery({ queryKey: ["starter"], queryFn: () => get<string[]>("/starter") });
  const examples = (starters.data ?? []).slice(0, 3);
  useEffect(() => { if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" }); }, [hash]);

  const sections: Section[] = [
    { id: "start", title: "Start here", icon: Lightbulb, body: (
      <>
        <ol className="steps big">
          <li><b>Ask</b> for a report in your own words, the way you would ask a colleague.</li>
          <li><b>Check</b> the answer: the rows, where it came from, and how ReBo read your question.</li>
          <li><b>Say if it is right.</b> ReBo learns from it, for you first, and gets faster and more accurate the more your team uses it.</li>
        </ol>
        {examples.length > 0 && <div className="tries"><span className="muted small">Try one of these:</span>{examples.map((q) => <Try key={q} q={q} />)}</div>}
      </>
    ) },
    { id: "asking", title: "Asking well", icon: MessageSquareText, body: (
      <ul className="tips">
        <li><b>Name the thing and the filter.</b> “Open maintenance requests per building”, not “requests?”.</li>
        <li><b>Say the period</b> if it matters: “last month”, “since January”. Or set a default once on <Link to="/knowledge#defaults">Knowledge → My defaults</Link>.</li>
        <li><b>Use your words.</b> If ReBo does not know a word, it asks once, with the options as buttons.</li>
        <li><b>Follow up</b> in the same conversation: “only the closed ones”, “per month instead”.</li>
      </ul>
    ) },
    { id: "reading", title: "Reading an answer", icon: Eye, body: (
      <>
        <dl className="defs">
          <dt><span className="pill verified"><span className="dot" />Verified</span></dt><dd>Checked by an admin and shared with everyone.</dd>
          <dt><span className="pill yours"><span className="dot" />Your report</span></dt><dd>One you confirmed before, run again on today's data. No model was asked.</dd>
          <dt><span className="pill adapted"><span className="dot" />From saved knowledge</span></dt><dd>Built from a saved report or definition.</dd>
          <dt><span className="pill"><span className="dot" />New</span></dt><dd>Written fresh for this question. Glance at how it was read.</dd>
        </dl>
        <ul className="tips">
          <li><b>What the query does</b> lists the query as plain steps, so you can check it without reading SQL.</li>
          <li><b>How I read your question</b> lists every choice ReBo made. A line starting with <b>Check</b> is something a second reviewer was unsure about.</li>
          <li><b>Table or chart:</b> answers by date or category can switch to a chart. Shade every other row, or open charts first, on <Link to="/me#preferences">You → How ReBo looks</Link>.</li>
        </ul>
      </>
    ) },
    { id: "fixing", title: "When an answer is wrong", icon: Hand, body: (
      <ul className="tips icons">
        <li><CircleAlert /><span>Press <b>No, fix it</b> and say what should change, in words: “only count active tenants”. ReBo redoes the report.</span></li>
        <li><Undo2 /><span>Pressed the wrong button? <b>Undo my feedback</b> puts everything back.</span></li>
        <li><Users /><span>If the answer comes from shared knowledge you cannot change, use <b>⋯ → Ask an admin to fix this</b>. You see the reply under <Link to="/knowledge#requests">Knowledge → My requests</Link>.</span></li>
      </ul>
    ) },
    { id: "teaching", title: "Teaching ReBo", icon: BookMarked, body: (
      <ul className="tips icons">
        <li><BadgeCheck /><span><b>Yes, this is right</b> saves the report for you. The same question next time is answered instantly, at no cost.</span></li>
        <li><Lightbulb /><span>When you explain a word, ReBo offers <b>Remember this?</b> Accept it and it applies to your future questions.</span></li>
        <li><BookMarked /><span>See, edit, share or withdraw everything you taught on <Link to="/knowledge">Knowledge</Link>. Nothing is ever deleted; every change can be undone.</span></li>
        <li><Users /><span>What you teach affects only you until three people independently agree and an admin shares it.</span></li>
      </ul>
    ) },
    { id: "reuse", title: "Getting more from a report", icon: ListChecks, body: (
      <ul className="tips icons">
        <li><RotateCcw /><span><b>Run again on today's data</b> from the ⋯ menu.</span></li>
        <li><Pin /><span><b>Pin</b> a report to run it from <Link to="/me#pinned">You → Pinned</Link>.</span></li>
        <li><Timer /><span><b>Send me this regularly</b>: daily, weekdays or a day of the week. No model is asked, so it costs nothing.</span></li>
        <li><MousePointerClick /><span>On a summary (one row per group), <b>select a row</b> to see the records behind it.</span></li>
        <li><Download /><span><b>Download CSV</b>, copy the table, or filter the rows in place.</span></li>
      </ul>
    ) },
    { id: "safety", title: "Safety and limits", icon: ShieldCheck, body: (
      <ul className="tips">
        <li><b>Read-only.</b> ReBo can only read. Every query is checked before it runs and nothing can change your data.</li>
        <li><b>Protected data</b> such as passwords and secrets is detected and never shown.</li>
        <li><b>ReBo is an AI and can misread a question.</b> The data it shows is real, but the question it answered may not be quite yours: that is why it always says how it read it.</li>
      </ul>
    ) },
    { id: "shortcuts", title: "Shortcuts", icon: Keyboard, body: (
      <p>⌘K to search, ask or jump anywhere; ⌘/ for your conversations; ? for this page. All of them on <Link to="/me#shortcuts">You → Shortcuts</Link>.</p>
    ) },
    { id: "admins", title: "For admins", icon: Users, admin: true, body: (
      <div className="gos">
        <Go to="/review">Review what people agree on, share or withdraw it, answer requests</Go>
        <Go to="/admin">Edit everything learned as one file; see a question as another person</Go>
        <Go to="/insights">Health checks, measured accuracy, feedback and cost</Go>
      </div>
    ) },
    { id: "owners", title: "For owners", icon: ShieldCheck, owner: true, body: (
      <div className="gos"><Go to="/config">Change the configuration: checked before saving, every version can be restored</Go></div>
    ) },
  ];
  const shown = sections.filter((s) => (!s.admin || me?.is_admin) && (!s.owner || me?.is_owner));

  return (
    <div className="page help">
      <PageHead title="How to use ReBo" lede="Ask for reports in plain words, check how they were read, and teach ReBo as you go. Two minutes to read; everything links to where it lives." />
      <div className="helpgrid">
        <Toc items={shown} />
        <div className="helpbody">
          {shown.map((s) => (
            <section key={s.id} id={s.id} className="card helpsec">
              <h2><s.icon />{s.title}</h2>
              {s.body}
            </section>
          ))}
          <p className="aboutlink"><Link to="/about">About ReBo<ArrowRight /></Link></p>
        </div>
      </div>
    </div>
  );
}

// The contents as a floating glass rail; the section you are reading is lit (scroll spy).
function Toc({ items }: { items: { id: string; title: string; icon: any }[] }) {
  const [at, setAt] = useState(items[0]?.id);
  useEffect(() => {
    const io = new IntersectionObserver((es) => {
      const top = es.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setAt(top.target.id);
    }, { rootMargin: "-90px 0px -60% 0px" });
    items.forEach((s) => { const el = document.getElementById(s.id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [items]);
  return (
    <Glass as="nav" className="toc" aria-label="On this page" strength={20}>
      {items.map((s) => <a key={s.id} href={`#${s.id}`} className={at === s.id ? "on" : undefined} aria-current={at === s.id ? "location" : undefined}><s.icon />{s.title}</a>)}
    </Glass>
  );
}
