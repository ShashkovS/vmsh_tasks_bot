import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

import { assertSafeProductionBuild } from '../../vite-production-guard'

const apiOrigin = process.env.VMSH_API_ORIGIN ?? 'http://127.0.0.1:8180'

export default defineConfig(({ command, mode }) => {
  assertSafeProductionBuild({ command, mode }, import.meta.dirname)

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
        injectManifest: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg,webp,woff,woff2}'],
          // Precache only the font subsets this Russian app renders (latin + cyrillic).
          globIgnores: [
            '**/*greek*.{woff,woff2}',
            '**/*vietnamese*.{woff,woff2}',
            '**/*latin-ext*.{woff,woff2}',
            '**/*cyrillic-ext*.{woff,woff2}',
          ],
        },
        registerType: 'prompt',
        injectRegister: 'auto',
        includeAssets: ['icon.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png'],
        manifest: {
          id: '/student/',
          name: 'ВМШ 179 — школьник',
          short_name: 'ВМШ 179',
          description: 'Задачи, ответы, проверка и прогресс школьника ВМШ 179',
          lang: 'ru',
          start_url: '/student/',
          scope: '/student/',
          display: 'standalone',
          background_color: '#edeff1',
          theme_color: '#205f7d',
          icons: [
            { src: '/student/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
            { src: '/student/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
            { src: '/student/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
            {
              src: '/student/icon-maskable-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
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
        '/pwa-content-assets': { target: apiOrigin, changeOrigin: false },
        '/student/api': { target: apiOrigin, changeOrigin: false },
        '/student/ws': { target: apiOrigin, changeOrigin: false, ws: true },
      },
    },
    preview: {
      proxy: {
        '/pwa-content-assets': { target: apiOrigin, changeOrigin: false },
        '/student/api': { target: apiOrigin, changeOrigin: false },
        '/student/ws': { target: apiOrigin, changeOrigin: false, ws: true },
      },
    },
  }
})
