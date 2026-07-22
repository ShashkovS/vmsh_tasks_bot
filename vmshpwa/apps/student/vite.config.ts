import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const apiOrigin = process.env.VMSH_API_ORIGIN ?? 'http://127.0.0.1:8180'

export default defineConfig(({ command }) => {
  if (
    command === 'build' &&
    (process.env.VITE_ENABLE_MSW === 'true' || process.env.VITE_PROTOTYPE === 'true')
  ) {
    throw new Error('MSW and prototype mode must never be enabled in a production build')
  }

  return {
    base: '/student/',
    plugins: [
      tanstackRouter({ target: 'react', autoCodeSplitting: true }),
      react(),
      tailwindcss(),
      VitePWA({
        strategies: 'injectManifest',
        srcDir: 'src',
        filename: 'sw.ts',
        registerType: 'prompt',
        injectRegister: 'auto',
        includeAssets: ['icon.svg'],
        manifest: {
          id: '/student/',
          name: 'ВМШ 179 — школьник',
          short_name: 'ВМШ 179',
          description: 'Задачи, ответы, проверка и прогресс школьника ВМШ 179',
          lang: 'ru',
          start_url: '/student/',
          scope: '/student/',
          display: 'standalone',
          background_color: '#f7f4ed',
          theme_color: '#356a91',
          icons: [
            {
              src: '/student/icon.svg',
              sizes: 'any',
              type: 'image/svg+xml',
              purpose: 'any maskable',
            },
          ],
        },
        devOptions: {
          enabled: process.env.VMSH_PWA_DEV_SW === '1',
          type: 'module',
          navigateFallback: '/student/',
        },
      }),
    ],
    server: {
      proxy: {
        '/student/api': { target: apiOrigin, changeOrigin: true },
        '/student/ws': { target: apiOrigin, changeOrigin: true, ws: true },
      },
    },
  }
})
