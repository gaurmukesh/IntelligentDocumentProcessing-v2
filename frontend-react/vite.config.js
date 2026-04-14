import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  server: {
    port: 3000,
    proxy: {
      '/api/fastapi': {
        target: process.env.VITE_FASTAPI_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/fastapi/, ''),
      },
      '/api/erp': {
        target: process.env.VITE_ERP_URL || 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/erp/, ''),
      },
    },
  },
})
