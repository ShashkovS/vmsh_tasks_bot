/// <reference lib="webworker" />

import { clientsClaim } from 'workbox-core'
import { cleanupOutdatedCaches, matchPrecache, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst } from 'workbox-strategies'

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision?: string }>
}

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
  ({ request, url }) =>
    request.method === 'GET' && url.pathname.startsWith('/student/media/generated/'),
  new CacheFirst({ cacheName: 'vmsh-student-generated-media-v1' }),
)

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') void self.skipWaiting()
})
