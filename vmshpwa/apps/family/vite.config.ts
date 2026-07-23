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
    base: '/family/',
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
            '**/*greek*.woff2',
            '**/*vietnamese*.woff2',
            '**/*latin-ext*.woff2',
            '**/*cyrillic-ext*.woff2',
          ],
        },
        registerType: 'prompt',
        injectRegister: 'auto',
        includeAssets: ['icon.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png'],
        manifest: {
          id: '/family/',
          name: 'ВМШ 179 — семья',
          short_name: 'ВМШ Семья',
          description: 'Расписание, прогресс и новости ВМШ 179 для семьи',
          lang: 'ru',
          start_url: '/family/',
          scope: '/family/',
          display: 'standalone',
          background_color: '#edeff1',
          theme_color: '#205f7d',
          icons: [
            { src: '/family/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
            { src: '/family/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
            { src: '/family/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
            {
              src: '/family/icon-maskable-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
        },
        devOptions: {
          enabled: process.env.VMSH_PWA_DEV_SW === '1',
          type: 'module',
          navigateFallback: '/family/',
        },
      }),
    ],
    server: {
      proxy: {
        '/family/api': { target: apiOrigin, changeOrigin: true },
        '/family/ws': { target: apiOrigin, changeOrigin: true, ws: true },
      },
    },
    preview: {
      proxy: {
        '/family/api': { target: apiOrigin, changeOrigin: true },
        '/family/ws': { target: apiOrigin, changeOrigin: true, ws: true },
      },
    },
  }
})
