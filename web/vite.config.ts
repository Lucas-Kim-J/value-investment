import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
  build: { outDir: "dist", sourcemap: false },
});
