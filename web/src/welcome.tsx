// The first screen, shown once on a machine without a company login: your name and your role. Each
// role says what it unlocks, cumulatively, so the difference is visible at a glance. In production the
// login proxy (or JWT) decides who you are and this screen never appears.
import { ArrowRight, Check, Crown, Info, ShieldCheck, Sparkles, UserRound, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { Label, Radio, RadioGroup } from "react-aria-components";
import { setIdentity, type Identity } from "./api";
import { Wordmark } from "./brand";
import { Glass } from "./glass";

const ROLES: { id: Identity["role"]; name: string; icon: LucideIcon; gist: string; base?: string; unlocks: string[] }[] = [
  { id: "user", name: "Member", icon: UserRound, gist: "Ask for reports and get answers you can check.",
    unlocks: ["Ask in plain words", "Confirm or correct answers", "Teach your own terms", "Pin and schedule reports"] },
  { id: "admin", name: "Admin", icon: ShieldCheck, gist: "Decide what everyone can rely on.", base: "Everything a member can, plus",
    unlocks: ["Share what people agree on", "Edit or undo any knowledge", "Answer people's requests", "See health and cost"] },
  { id: "owner", name: "Owner", icon: Crown, gist: "Look after the setup itself.", base: "Everything an admin can, plus",
    unlocks: ["Change the configuration", "Roll back any change"] },
];

export function Welcome() {
  const [name, setName] = useState("");
  const [role, setRole] = useState<Identity["role"]>("user");
  const ready = name.trim().length > 0;
  return (
    <div className="welcome">
      <div className="aurora" aria-hidden><span /><span /><span /></div>
      <Glass as="main" className="welcomecard" strength={40}>
        <header className="whead">
          <Wordmark size={34} />
          <h1>Reports in plain words.</h1>
          <p>Ask for any report the way you would ask a colleague. ReBo shows the rows, how it read you, and
            where the answer came from, and it <b>gets sharper every time you confirm or correct it</b>.</p>
        </header>

        <form onSubmit={(e) => { e.preventDefault(); if (ready) setIdentity({ user: name.trim(), role }); }}>
          <label className="wfield">
            <span>What should ReBo call you?</span>
            <input className="winput" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" aria-label="Your name" />
          </label>

          <RadioGroup className="roles" value={role} onChange={(v) => setRole(v as Identity["role"])} aria-label="Your role">
            <Label className="wlabel">How will you use it?</Label>
            <div className="rolegrid">
              {ROLES.map((r) => (
                <Radio key={r.id} value={r.id} className="rolecard">
                  {({ isSelected }) => (
                    <>
                      <span className="rtop">
                        <span className="ricon"><r.icon /></span>
                        <span className="rname">{r.name}</span>
                        <span className={`rtick${isSelected ? " on" : ""}`} aria-hidden>{isSelected && <Check />}</span>
                      </span>
                      <span className="rgist">{r.gist}</span>
                      {r.base && <span className="rbase">{r.base}</span>}
                      <span className="runlocks">{r.unlocks.map((u) => <span key={u} className="unlock">{u}</span>)}</span>
                    </>
                  )}
                </Radio>
              ))}
            </div>
          </RadioGroup>

          <button className="btn primary wgo" type="submit" disabled={!ready}>
            {ready ? `Start as ${ROLES.find((r) => r.id === role)!.name.toLowerCase()}` : "Start"}<ArrowRight />
          </button>
        </form>

        <p className="wnotice" role="note"><Info />This is a preview sign-in. In your company's setup you sign in with your usual
          work login, which decides your role, and this screen goes away.</p>
        <p className="wlearn"><Sparkles />Nothing about your business is configured: ReBo learns it from your data and from
          your feedback, so it improves the more your team uses it.</p>
      </Glass>
    </div>
  );
}
