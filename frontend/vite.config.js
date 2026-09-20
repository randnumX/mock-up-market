import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Bind to 0.0.0.0, not just localhost - harmless natively, required for
    // the containerized dev mode (docker-compose.yml's "dev" profile) so the
    // host machine can actually reach the dev server through the port mapping.
    host: true,
    proxy: {
      '/api': {
        // VITE_PROXY_TARGET lets the dev-profile container point this at
        // the backend-dev service by Docker DNS name instead of localhost,
        // which inside a container refers to itself, not the backend
        // container. Native dev (no env var set) is unaffected.
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
