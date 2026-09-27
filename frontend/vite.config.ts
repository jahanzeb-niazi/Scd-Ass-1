/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Runtime configuration (ADR 0002): the app only ever calls the relative path
// /api. In production nginx proxies /api to the backend; in development the
// Vite dev server does the same. No backend URL is baked into the bundle.
// API_PROXY_TARGET is read by the dev server only (Node side), never by the bundle.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: apiTarget, changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    restoreMocks: true,
    css: false,
  },
});
