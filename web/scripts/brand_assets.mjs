// Renders the link-preview image (og.png, 1200x630) and the PNG icons from logo.svg into web/public.
//   node scripts/brand_assets.mjs
// Messengers (WhatsApp, Slack, Teams, iMessage, LinkedIn) ignore SVG icons and need an absolute PNG image.
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";

const pub = new URL("../public/", import.meta.url).pathname;
const logo = readFileSync(`${pub}logo.svg`, "utf8");
const b = await chromium.launch();

// ---- icons ----
for (const [name, size, pad] of [["favicon-32.png", 32, 0], ["apple-touch-icon.png", 180, 0], ["icon-192.png", 192, 0], ["icon-512.png", 512, 0]]) {
  const p = await b.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
  await p.setContent(`<html><body style="margin:0;background:transparent">${logo.replace("<svg ", `<svg width="${size - pad * 2}" height="${size - pad * 2}" style="display:block;margin:${pad}px" `)}</body></html>`);
  await p.screenshot({ path: `${pub}${name}`, omitBackground: name !== "apple-touch-icon.png" });
  await p.close();
}

// ---- link preview ----
const og = `<!doctype html><html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; margin: 0; }
  body { width: 1200px; height: 630px; overflow: hidden; background: #0d1b24; color: #eef2f5;
         font-family: -apple-system, "SF Pro Display", "Inter", system-ui, sans-serif; -webkit-font-smoothing: antialiased; }
  .field { position: absolute; border-radius: 50%; filter: blur(70px); opacity: .55; }
  .a { width: 620px; height: 480px; left: -160px; top: -180px; background: #3fd0a6; }
  .b { width: 520px; height: 420px; right: -120px; top: 40px; background: #e6a93c; opacity: .42; }
  .c { width: 700px; height: 420px; left: 300px; bottom: -300px; background: #4078c8; opacity: .5; }
  .left { position: absolute; left: 72px; top: 64px; width: 560px; }
  .brand { display: flex; align-items: center; gap: 18px; font-weight: 720; font-size: 44px; line-height: 1; letter-spacing: -0.035em; }
  .brand svg { width: 72px; height: 72px; filter: drop-shadow(0 8px 20px rgba(0,0,0,.35)); }
  h1 { margin-top: 44px; font-weight: 760; font-size: 60px; line-height: 1.02; letter-spacing: -0.045em; }
  .sub { margin-top: 20px; font-size: 22px; line-height: 1.45; color: #b8c4cc; }
  .tags { position: absolute; left: 72px; bottom: 60px; display: flex; gap: 10px; }
  .tag { padding: 10px 16px; border-radius: 999px; font-weight: 640; font-size: 18px; color: #eef2f5;
         background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.16); }
  .card { position: absolute; right: 64px; top: 92px; width: 456px; padding: 22px; border-radius: 28px;
          background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.22);
          box-shadow: inset 0 1px 0 rgba(255,255,255,.35), 0 30px 60px -20px rgba(0,0,0,.6); backdrop-filter: blur(18px) saturate(1.6); }
  .q { font-size: 21px; font-weight: 650; letter-spacing: -0.01em; }
  .q span { display: inline-grid; place-items: center; width: 30px; height: 30px; margin-right: 10px; border-radius: 50%;
            background: #3fd0a6; color: #04251b; font-size: 15px; font-weight: 800; vertical-align: 2px; }
  .read { display: inline-block; margin-top: 16px; padding: 8px 12px; border-radius: 12px; font-size: 15px;
          background: rgba(230,169,60,.18); border: 1px solid rgba(230,169,60,.45); color: #f5d79b; }
  .read b { color: #fff; font-weight: 700; }
  table { width: 100%; margin-top: 16px; border-collapse: collapse; font-size: 17px; }
  th { text-align: left; font-weight: 600; color: #9fb0bb; font-size: 14px; padding: 0 0 8px; }
  th.n, td.n { text-align: right; font-variant-numeric: tabular-nums; }
  td { padding: 10px 0; border-top: 1px solid rgba(255,255,255,.12); }
  .ok { margin-top: 16px; display: flex; gap: 8px; }
  .ok span { padding: 8px 12px; border-radius: 11px; font-size: 14px; font-weight: 650; }
  .yes { background: rgba(63,208,166,.2); color: #8ff0cf; border: 1px solid rgba(63,208,166,.45); }
  .no { background: rgba(255,255,255,.07); color: #d5dde2; border: 1px solid rgba(255,255,255,.16); }
</style></head><body>
  <div class="field a"></div><div class="field b"></div><div class="field c"></div>
  <div class="left">
    <div class="brand">${logo}<span>ReBo</span></div>
    <h1>Reports in plain words, from any SQL database.</h1>
    <p class="sub">Ask the way you would ask a colleague. It reads your database itself and learns from every confirmation and correction.</p>
  </div>
  <div class="tags"><span class="tag">Self-learning</span><span class="tag">Plug and play</span><span class="tag">Read-only</span></div>
  <div class="card">
    <p class="q"><span>1</span>Which customers owe us the most?</p>
    <p class="read">Read as <b>invoices not yet paid</b>, in rupees</p>
    <table>
      <tr><th>Customer</th><th class="n">Outstanding</th></tr>
      <tr><td>Sarma Power Enterprises</td><td class="n">₹4,82,10,500</td></tr>
      <tr><td>Bailey Grid plc</td><td class="n">₹3,96,44,120</td></tr>
      <tr><td>Nerger Energy AG</td><td class="n">₹2,71,09,880</td></tr>
    </table>
    <div class="ok"><span class="yes">✓ Yes, this is right</span><span class="no">No, fix it</span></div>
  </div>
</body></html>`;
const p = await b.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await p.setContent(og);
await p.waitForTimeout(300);
await p.screenshot({ path: `${pub}og.png` });
await b.close();
console.log("wrote og.png, favicon-32.png, apple-touch-icon.png, icon-192.png, icon-512.png");
