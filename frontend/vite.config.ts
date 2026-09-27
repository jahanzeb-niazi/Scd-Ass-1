import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // TODO(you): decide dev-time proxying to the backend here if you go the
    // "nginx/vite proxies /api" route for runtime config (see
    // docs/adr/0002-frontend-runtime-config.md and src/config.ts).
    // proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
  },
});
