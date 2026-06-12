/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// TDD Guard reporters write to <repoRoot>/.claude/tdd-guard/data/ — repoRoot is web/'s parent.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// SPA that deploys as static files (vite build → dist → rsync to nginx).
// In dev, proxy /api to the running backend (docker stack at :8080) so session
// cookies are same-origin. /content serves the markdown docs for react-markdown.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    reporters: [
      "default",
      ["tdd-guard-vitest", { projectRoot: repoRoot }],
    ],
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        // Split rarely-changing vendor cores into their own long-cache chunks.
        // react-markdown's ecosystem is intentionally left auto-split so it stays a
        // deferred chunk (loaded with the chat / doc / markdown routes, not on first paint).
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("framer-motion") || id.includes("/motion-dom/") || id.includes("/motion-utils/")) return "motion";
          if (id.includes("/react-dom/") || id.includes("/scheduler/") || id.includes("react-router") || id.includes("@remix-run")) return "react";
        },
      },
    },
  },
});
