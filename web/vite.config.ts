import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built into web/dist and served by the bot at /app (api.create_app). `npm run dev` proxies the API.
export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8080" } },
});
