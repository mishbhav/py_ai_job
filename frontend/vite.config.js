import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In GitHub Codespaces, the dev server is reached via a forwarded
// *.app.github.dev URL rather than localhost, so we allow all hosts
// during development.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: true,
    port: 5173,
  },
});
