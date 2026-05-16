import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
      port: 5173,
      // Dev proxy: only active during `npm run dev`
      // In production, VITE_API_URL points directly to the backend host.
      proxy: env.VITE_API_URL
        ? undefined
        : {
            "/api": {
              target: "http://localhost:8000",
              changeOrigin: true,
              rewrite: (p) => p.replace(/^\/api/, ""),
            },
          },
    },
  };
});
