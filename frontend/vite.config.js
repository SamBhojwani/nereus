import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: /api/* -> the FastAPI backend, so the frontend never hardcodes a host.
// In production set VITE_API_BASE to the deployed backend URL instead.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
