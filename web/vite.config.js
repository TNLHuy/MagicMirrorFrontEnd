import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/cors': 'http://127.0.0.1:8080',
    },
  },
  plugins: [
    react(),
    tailwindcss(),
  ],
})
