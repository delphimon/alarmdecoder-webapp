import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendOrigin = process.env.VITE_BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
const backendWsOrigin = backendOrigin.replace(/^http/, "ws");

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backendOrigin,
      "/health": backendOrigin,
      "/ready": backendOrigin,
      "/ws": {
        target: backendWsOrigin,
        ws: true,
      },
    },
  },
});
