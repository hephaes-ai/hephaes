import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  define: {
    "process.env.NEXT_PUBLIC_BACKEND_BASE_URL": JSON.stringify(
      process.env.NEXT_PUBLIC_BACKEND_BASE_URL ?? "",
    ),
  },
  resolve: {
    alias: [
      {
        find: "@/lib/app-routing",
        replacement: path.resolve(
          __dirname,
          "src/lib/app-routing.react-router.tsx",
        ),
      },
      {
        find: "@",
        replacement: path.resolve(__dirname, "src"),
      },
    ],
  },
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
