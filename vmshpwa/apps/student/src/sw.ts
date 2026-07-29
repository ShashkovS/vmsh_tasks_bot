/// <reference lib="webworker" />

import { clientsClaim, setCacheNameDetails } from 'workbox-core'
import type { WorkboxPlugin } from 'workbox-core'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { ExpirationPlugin } from 'workbox-expiration'
import { cleanupOutdatedCaches, matchPrecache, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst } from 'workbox-strategies'

import {
  immutableContentAssetNavigationPattern,
  isAudienceRoute,
  parseAudiencePushPayload,
  shouldCacheRecentMediaRequest,
} from '@vmsh/offline'

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision?: string }>
}

const publicMediaOrigin = import.meta.env.VITE_PUBLIC_MEDIA_ORIGIN
const twoWeeksInSeconds = 14 * 24 * 60 * 60
const legacyUnscopedPrecacheName = 'vmsh-179-student-precache-v1'
const legacyRecentMediaCacheName = 'vmsh-student-recent-media-v1'
const reservedNavigationPaths = [
  immutableContentAssetNavigationPattern,
  /^\/student\/(?:api|ws|assets|media)(?:\/|$)/,
  /^\/student\/(?:sw\.js|manifest\.webmanifest|icon[^/]*)$/,
  /^\/student\/.*\.(?:avif|css|csv|eot|gif|html|ico|jpe?g|js|json|map|mjs|otf|pdf|png|svg|ttf|txt|wasm|webmanifest|webp|woff2?|xml|zip)$/,
]

// Both PWAs share one production origin, so Workbox defaults are not an
// acceptable ownership boundary. See Phase 0 and runtime-isolation.spec.ts.
setCacheNameDetails({
  prefix: 'vmsh-179-student',
  precache: 'precache',
  // Workbox cleanupOutdatedCaches identifies owned legacy caches by the
  // registration scope. Keep it in the suffix while adding our own migration
  // version, otherwise a future v2 worker would leak the v1 precache forever.
  suffix: `${self.registration.scope}v1`,
})
clientsClaim()
void cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)
self.addEventListener('activate', (event) => {
  // One-time cleanup for the Phase-0 prototype names. Exact audience-owned
  // names preserve the Student/Family boundary proven by runtime-isolation.spec.ts.
  event.waitUntil(
    Promise.all([
      caches.delete(legacyUnscopedPrecacheName),
      caches.delete(legacyRecentMediaCacheName),
    ]),
  )
})

registerRoute(
  new NavigationRoute(
    async () => {
      const shell =
        (await matchPrecache('/student/index.html')) ?? (await matchPrecache('/student/'))
      return shell ?? fetch('/student/')
    },
    {
      // A navigation request is still capable of reaching API/static URLs.
      // Keep reserved namespaces on the network so a 404/JSON response can
      // never be replaced with the application shell. Phase 0 E2E activates
      // the worker before probing these boundaries.
      denylist: reservedNavigationPaths,
    },
  ),
)
registerRoute(
  ({ request, url }) => {
    return shouldCacheRecentMediaRequest({
      method: request.method,
      destination: request.destination,
      url,
      applicationOrigin: self.location.origin,
      audienceGeneratedMediaPrefix: '/student/media/generated/',
      publicMediaOrigin,
    })
  },
  new CacheFirst({
    cacheName: 'vmsh-179-student-recent-media-v1',
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
  const message: unknown = event.data
  if (
    typeof message === 'object' &&
    message !== null &&
    'type' in message &&
    message.type === 'SKIP_WAITING'
  ) {
    event.waitUntil(self.skipWaiting())
  }
})

self.addEventListener('push', (event) => {
  if (!event.data) return
  const payload = parseAudiencePushPayload(event.data.text(), 'student')
  if (!payload) return
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      if (windows.some((client) => client.visibilityState === 'visible')) return
      await self.registration.showNotification(payload.title, {
        body: payload.body,
        data: { route: payload.route },
        icon: '/student/icon-192.png',
        tag: payload.eventId,
        silent: payload.silent,
      })
    })(),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const notificationData = event.notification.data as unknown
  const route =
    typeof notificationData === 'object' && notificationData !== null && 'route' in notificationData
      ? notificationData.route
      : null
  if (!isAudienceRoute(route, 'student')) return
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const owned = windows.find((client) => new URL(client.url).pathname.startsWith('/student/'))
      if (owned) {
        await owned.navigate(route)
        await owned.focus()
        return
      }
      await self.clients.openWindow(route)
    })(),
  )
})
