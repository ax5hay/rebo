// About ReBo: what the app is, how a question becomes a report, what it never does, and what it is
// built with. Reached from Help, You and the command palette rather than the main tabs.
import { ArrowUpRight, Ban, Database, EyeOff, MessageSquareText, ShieldCheck, Sparkles, Wand2 } from "lucide-react";
import { Link } from "react-router";
import { Wordmark } from "../brand";
import { Glass } from "../glass";

const FLOW = [
  { t: "Connect", d: "Point ReBo at a database with a read-only login. That and about ten lines of settings are all it needs." },
  { t: "Read", d: "It reads the tables, keys and stored values itself, and works out which columns hold secrets." },
  { t: "Ask", d: "People ask in their own words. If a question can be read two ways, ReBo asks once, with real options." },
  { t: "Check", d: "Every query is checked and run before you see it, with the rows, how your question was read, and the query." },
  { t: "Learn", d: "Confirmations and corrections become knowledge, for you first, for everyone once people agree." },
];

const NEVER = [
  { icon: Database, t: "Change your data", d: "Read-only at every layer: the query guard, the session and the login." },
  { icon: EyeOff, t: "Show secrets", d: "Passwords, tokens and account numbers are found automatically and kept out." },
  { icon: Ban, t: "Guess silently", d: "Every choice it made is written under the answer, and one switch changes it." },
  { icon: Wand2, t: "Need configuring", d: "Nothing about your business is set up by hand; meaning comes from use." },
];

export default function AboutPage() {
  return (
    <div className="page about">
      <Glass as="section" className="abouthero" strength={36}>
        <Wordmark size={40} />
        <h1>A reports bot that learns your company.</h1>
        <p>ReBo turns plain questions into one read-only query and the rows that answer them. It works on any SQL
          database and starts knowing nothing about your business; every answer someone confirms or corrects makes the
          next one better, so it improves the more your team uses it.</p>
      </Glass>

      <section className="aboutsec">
        <h2>From question to report</h2>
        <ol className="flow">{FLOW.map((s, i) => <li key={s.t}><span className="fnum">{i + 1}</span><b>{s.t}</b><span>{s.d}</span></li>)}</ol>
      </section>

      <section className="aboutsec">
        <h2>What it will never do</h2>
        <div className="nevergrid">{NEVER.map((n) => <div key={n.t} className="card never"><n.icon /><b>{n.t}</b><span>{n.d}</span></div>)}</div>
      </section>

      <section className="aboutsec two">
        <div className="card">
          <h2><Sparkles />If this is a demo</h2>
          <p>The demo company, Orbitra Energy Systems, is invented: 221 tables and about three million rows of synthetic
            Indian and international data. Ask it anything; nothing you do here touches a real business.</p>
          <p><Link to="/help">How to use ReBo</Link></p>
        </div>
        <div className="card">
          <h2><ShieldCheck />Built with</h2>
          <ul className="builtwith">
            <li>Claude for reading questions and writing queries</li>
            <li>A syntax-tree guard that only lets reads through</li>
            <li>Local search over your schema and stored values</li>
            <li>PostgreSQL or SQLite for what it learns</li>
          </ul>
        </div>
      </section>

      <footer className="madeby">
        <MessageSquareText />
        <span>Designed and built by <a href="https://akshaybajpai.com" target="_blank" rel="noopener">Akshay Bajpai</a>.</span>
        <a className="cardlink" href="https://akshaybajpai.com/card" target="_blank" rel="noopener">Say hello<ArrowUpRight /></a>
      </footer>
    </div>
  );
}
