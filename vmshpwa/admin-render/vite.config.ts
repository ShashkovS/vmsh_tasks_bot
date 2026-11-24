import { defineConfig } from 'vite'
import { i18nPlugins } from '../vite-i18n'

export default defineConfig({
  plugins: i18nPlugins(),
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  ssr: { noExternal: true },
  build: {
    ssr: 'admin-render/render.tsx',
    outDir: 'admin-render/dist',
    rolldownOptions: {
      output: { format: 'cjs', entryFileNames: 'render.cjs', codeSplitting: false },
    },
  },
})
