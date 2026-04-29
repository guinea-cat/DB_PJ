import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/flights": "http://localhost:8000",
      "/tickets": "http://localhost:8000",
      "/payments": "http://localhost:8000",
      "/waitlists": "http://localhost:8000",
      "/me": "http://localhost:8000",
      "/reference": "http://localhost:8000",
      "/admin": "http://localhost:8000",
      "/health": "http://localhost:8000"
    }
  }
});
