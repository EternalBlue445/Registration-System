import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Optional: proxy API calls in dev to avoid CORS config
      // "/api": { target: "http://localhost:8000", rewrite: (p) => p.replace(/^\/api/, "") }
    },
  },
});
