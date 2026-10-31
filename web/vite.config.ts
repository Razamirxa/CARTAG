import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = "http://localhost:4000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    // The browser talks only to this origin. The scan page (/t/CODE) and the API live on the
    // Python server, so they are forwarded. Origin is left untouched so the server's CSRF check
    // sees http://localhost:5173, the same value as PUBLIC_BASE_URL. The QR holds the link in
    // upper case, so a phone opens /T/CODE, which is forwarded too.
    proxy: {
      "/api": API,
      "/t": API,
      "/T": API,
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
