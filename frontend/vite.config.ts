import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:80",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-antd": ["antd", "@ant-design/icons"],
          "vendor-charts": ["recharts"],
          // html5-qrcode не включаем — он импортируется динамически (await import)
          // и попадёт в отдельный lazy-chunk автоматически
          "vendor-i18n": ["i18next", "react-i18next"],
          "vendor-query": ["@tanstack/react-query", "axios"],
        },
      },
    },
  },
});
