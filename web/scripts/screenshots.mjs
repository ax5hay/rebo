// Visual check (B-043): every page for each role, with a feedback / undo / request / edit flow,
// saved to docs/screenshots/. Needs a server with the UI: uv run python tests/web_server.py --ui --port 8770
//   node scripts/screenshots.mjs http://127.0.0.1:8770 ../docs/screenshots
import { chromium } from "@playwright/test";

const [base, out] = process.argv.slice(2);
const browser = await chromium.launch();
const shot = async (page, name) => page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
const issues = [];
const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
page.on("pageerror", (e) => issues.push(`pageerror: ${e.message}`));
page.on("console", (m) => m.type() === "error" && issues.push(`console: ${m.text()}`));
const settle = () => page.waitForTimeout(800);

// user: the NiceGUI Ask page, a report, feedback and undo, a fix request
await page.goto(`${base}/?user=alice`); await settle(); await shot(page, "01-user-ask-empty");
await page.getByPlaceholder("Ask for a report").fill("customers on hold, i.e. paused");
await page.keyboard.press("Enter");
await page.getByText("Here is Paused customers").waitFor({ timeout: 20000 }); await settle();
await shot(page, "02-user-report");
await page.getByRole("button", { name: /Yes/ }).first().click(); await settle(); await shot(page, "03-user-confirmed");
const undo = page.getByRole("button", { name: /Undo/ }).first();
if (await undo.count()) { await undo.click(); await settle(); await shot(page, "04-user-undone"); }
await page.getByRole("button", { name: "Request a fix" }).first().click(); await settle(); await shot(page, "05-user-request-dialog");
await page.keyboard.press("Escape");
await page.goto(`${base}/knowledge?user=alice`); await settle(); await shot(page, "06-user-my-knowledge");

// admin: queue, usage, preview; owner: configuration
await page.goto(`${base}/admin?user=ada&role=admin`); await settle(); await shot(page, "07-admin");
await page.goto(`${base}/review?user=ada&role=admin`); await settle(); await shot(page, "08-admin-review");
await page.goto(`${base}/config?user=olga&role=owner`); await settle(); await shot(page, "09-owner-config");
await page.goto(`${base}/config?user=alice`); await settle(); await shot(page, "10-user-config-denied");

// the React Ask page, if built
const app = await page.goto(`${base}/app/?user=bob`);
if (app && app.ok()) {
  await page.getByRole("textbox", { name: "Your question" }).fill("show me customers");
  await page.getByRole("button", { name: "Ask" }).click();
  await page.getByTestId("clarify").waitFor(); await shot(page, "11-react-clarify");
}
await browser.close();
console.log(JSON.stringify({ issues }));
