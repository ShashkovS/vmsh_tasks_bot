import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { brandingAssets } from '../../vite-branding'
import { i18nPlugins } from '../../vite-i18n'
import { assertSafeProductionBuild, buildProvenancePlugin } from '../../vite-production-guard'

export default defineConfig(({ command, mode }) => {
  const provenance = assertSafeProductionBuild({ command, mode }, import.meta.dirname)

  return {
    base: '/landing/',
    server: {
      proxy: {
        '/student/api': {
          target: process.env.VMSH_API_ORIGIN ?? 'http://127.0.0.1:8180',
          changeOrigin: false,
        },
      },
    },
    preview: {
      proxy: {
        '/student/api': {
          target: process.env.VMSH_API_ORIGIN ?? 'http://127.0.0.1:8180',
          changeOrigin: false,
        },
      },
    },
    plugins: [
      brandingAssets(),
      react(),
      ...i18nPlugins(),
      tailwindcss(),
      buildProvenancePlugin('landing', provenance),
    ],
  }
})
