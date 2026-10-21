import { defineConfig, devices } from "@playwright/test";

// Smoke tests of the Ask page against a bot with a scripted model (tests/web_server.py). No LLM.
// Chromium always; BROWSERS=all adds WebKit (Safari's engine) and Firefox (npx playwright install webkit firefox).
const all = process.env.BROWSERS === "all";
export default defineConfig({
  testDir: "tests",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:8765", headless: true },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    ...(all ? [{ name: "webkit", use: { ...devices["Desktop Safari"] } }, { name: "firefox", use: { ...devices["Desktop Firefox"] } }] : []),
  ],
  webServer: {
    command: "cd .. && uv run python tests/web_server.py --port 8765",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
