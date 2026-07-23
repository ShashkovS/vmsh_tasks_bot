import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const apiOrigin = process.env.VMSH_API_ORIGIN ?? 'http://127.0.0.1:8180'

export default defineConfig(({ command }) => {
  if (
    command === 'build' &&
    (process.env.VITE_ENABLE_MSW === 'true' || process.env.VITE_PROTOTYPE === 'true')
  ) {
    throw new Error('MSW and prototype mode must never be enabled in a production build')
  }

  return {
    base: '/staff/',
    plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true }), react(), tailwindcss()],
    server: {
      proxy: {
        '/staff/api': { target: apiOrigin, changeOrigin: true },
        '/staff/ws': { target: apiOrigin, changeOrigin: true, ws: true },
      },
    },
    preview: {
      proxy: {
        '/staff/api': { target: apiOrigin, changeOrigin: true },
        '/staff/ws': { target: apiOrigin, changeOrigin: true, ws: true },
      },
    },
  }
})
