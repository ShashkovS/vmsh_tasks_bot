import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { i18nPlugins } from '../../vite-i18n'
import { assertSafeProductionBuild, buildProvenancePlugin } from '../../vite-production-guard'

export default defineConfig(({ command, mode }) => {
  const provenance = assertSafeProductionBuild({ command, mode }, import.meta.dirname)

  return {
    base: '/landing/',
    plugins: [
      react(),
      ...i18nPlugins(),
      tailwindcss(),
      buildProvenancePlugin('landing', provenance),
    ],
  }
})
