import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built HMI is served by FastAPI from backend/app/static.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../backend/app/static", emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
