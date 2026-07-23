/// <reference lib="webworker" />

import { clientsClaim } from 'workbox-core'
import type { WorkboxPlugin } from 'workbox-core'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { ExpirationPlugin } from 'workbox-expiration'
import { cleanupOutdatedCaches, matchPrecache, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst } from 'workbox-strategies'

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision?: string }>
}

const publicMediaOrigin = import.meta.env.VITE_PUBLIC_MEDIA_ORIGIN
const twoWeeksInSeconds = 14 * 24 * 60 * 60

clientsClaim()
void cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

registerRoute(
  new NavigationRoute(
    async () => {
      const shell =
        (await matchPrecache('/student/index.html')) ?? (await matchPrecache('/student/'))
      return shell ?? fetch('/student/')
    },
    {
      denylist: [/\/api\//, /\/ws$/],
    },
  ),
)
registerRoute(
  ({ request, url }) => {
    if (request.method !== 'GET' || request.destination !== 'image') return false
    return (
      url.pathname.startsWith('/student/media/generated/') ||
      (Boolean(publicMediaOrigin) && url.origin === publicMediaOrigin)
    )
  },
  new CacheFirst({
    cacheName: 'vmsh-student-recent-media-v1',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }) as WorkboxPlugin,
      new ExpirationPlugin({
        maxAgeSeconds: twoWeeksInSeconds,
        maxEntries: 80,
        purgeOnQuotaError: true,
      }) as WorkboxPlugin,
    ],
  }),
)

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') void self.skipWaiting()
})
