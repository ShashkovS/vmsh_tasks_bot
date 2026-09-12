import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { assertSafeProductionBuild, buildProvenancePlugin } from '../../vite-production-guard'

const apiOrigin = process.env.VMSH_API_ORIGIN ?? 'http://127.0.0.1:8180'

export default defineConfig(({ command, mode }) => {
  const provenance = assertSafeProductionBuild({ command, mode }, import.meta.dirname)

  return {
    base: '/staff/',
    plugins: [
      tanstackRouter({ target: 'react', autoCodeSplitting: true }),
      react(),
      tailwindcss(),
      buildProvenancePlugin('staff', provenance),
    ],
    server: {
      proxy: {
        '/pwa-content-assets': { target: apiOrigin, changeOrigin: false },
        '/staff/api': { target: apiOrigin, changeOrigin: false },
        '/staff/ws': { target: apiOrigin, changeOrigin: false, ws: true },
      },
    },
    preview: {
      proxy: {
        '/pwa-content-assets': { target: apiOrigin, changeOrigin: false },
        '/staff/api': { target: apiOrigin, changeOrigin: false },
        '/staff/ws': { target: apiOrigin, changeOrigin: false, ws: true },
      },
    },
  }
})
