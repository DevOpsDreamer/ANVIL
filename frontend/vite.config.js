import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

/**
 * Vite config — localhost development (no Docker).
 *
 * The dev server runs on :5173 and proxies all /api requests to the
 * FastAPI backend running on :8000. Start the backend separately with:
 *   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: 'localhost',
    proxy: {
    "/api": {
      target: "http://127.0.0.1:8000",
      changeOrigin: true,
      },
    },
  },
})
