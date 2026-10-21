// Visual check of the product (B-043, redone for the React app): each page for each role, with a
// confirm / undo / request / teach flow, saved to docs/screenshots/. Against the scripted-model server:
//   uv run python tests/web_server.py --port 8770      then      node scripts/screenshots.mjs http://127.0.0.1:8770 ../docs/screenshots
import { chromium } from "@playwright/test";

const [base, out] = process.argv.slice(2);
const browser = await browser_();
const issues = [];

async function browser_() { return chromium.launch(); }
async function page(user, role, viewport = { width: 1280, height: 860 }) {
  const ctx = await browser.newContext({ viewport });
  await ctx.addInitScript(([u, r]) => localStorage.setItem("rebo.identity", JSON.stringify({ user: u, role: r })), [user, role]);
  const p = await ctx.newPage();
  p.on("pageerror", (e) => issues.push(`pageerror: ${e.message}`));
  p.on("console", (m) => m.type() === "error" && issues.push(`console: ${m.text()}`));
  return p;
}
const shot = (p, name, full = false) => p.screenshot({ path: `${out}/${name}.png`, fullPage: full });
const ask = async (p, text) => {
  await p.getByRole("textbox", { name: "Your question" }).fill(text);
  await p.getByRole("button", { name: /^(Ask|Fix it)$/ }).click();
};

// a person asks, confirms, undoes, asks for a fix, and teaches something
const alice = await page("alice", "user");
await alice.goto(`${base}/app/`); await alice.waitForTimeout(600); await shot(alice, "01-start");
await ask(alice, "customers on hold, i.e. paused");
await alice.getByTestId("report").waitFor(); await alice.waitForTimeout(300); await shot(alice, "02-answer");
await alice.getByRole("button", { name: "Yes, this is right" }).click(); await alice.waitForTimeout(400); await shot(alice, "03-confirmed");
await alice.getByRole("button", { name: "Undo my feedback" }).click(); await alice.waitForTimeout(400);
await alice.getByRole("button", { name: "More actions" }).click(); await alice.waitForTimeout(250);
await shot(alice, "04a-more-actions");
await alice.getByRole("menuitem", { name: "Ask an admin to fix this" }).click(); await alice.waitForTimeout(300);
await alice.getByRole("textbox", { name: "What should change" }).fill("Paused customers should exclude test accounts.");
await shot(alice, "04-request-a-fix");
await alice.getByRole("button", { name: "Send to an admin" }).click(); await alice.waitForTimeout(400);
await ask(alice, "show me customers"); await alice.getByTestId("clarify").waitFor(); await alice.waitForTimeout(300); await shot(alice, "05-clarification");
await alice.goto(`${base}/app/knowledge`); await alice.waitForTimeout(800); await shot(alice, "06-what-i-taught");

// an admin reviews and checks insights
const ada = await page("ada", "admin");
await ada.goto(`${base}/app/review`); await ada.waitForTimeout(800); await shot(ada, "07-review");
await ada.goto(`${base}/app/admin`); await ada.waitForTimeout(600); await shot(ada, "08-admin");
await ada.goto(`${base}/app/insights`); await ada.waitForTimeout(2000); await shot(ada, "09-insights", true);

// the owner's configuration
const olga = await page("olga", "owner");
await olga.goto(`${base}/app/config`); await olga.waitForTimeout(800); await shot(olga, "10-configuration");

// a phone
const phone = await page("alice", "user", { width: 390, height: 844 });
await phone.goto(`${base}/app/`); await ask(phone, "customers on hold, i.e. paused");
await phone.getByTestId("report").waitFor(); await phone.waitForTimeout(300); await shot(phone, "11-phone-answer");

await browser.close();
console.log(JSON.stringify({ issues }));
