import { defineConfig } from "@playwright/test";

// Smoke tests of the Ask page against a bot with a scripted model (tests/web_server.py). No LLM.
export default defineConfig({
  testDir: "tests",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:8765", headless: true },
  webServer: {
    command: "cd .. && uv run python tests/web_server.py --port 8765",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
