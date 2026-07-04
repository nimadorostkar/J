import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, if VITE_API_BASE_URL is a relative path like "/api/v1",
// the proxy below forwards /api → http://localhost (nginx) so the
// browser sees a same-origin request and avoids CORS entirely.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_DEV_API_TARGET || 'http://localhost'
  return {
    plugins: [react()],
    server: {
      port: 5173,
      open: true,
      proxy: {
        '/api':   { target, changeOrigin: true },
        '/ws':    { target, changeOrigin: true, ws: true },
        '/media': { target, changeOrigin: true },
      },
    },
  }
})
