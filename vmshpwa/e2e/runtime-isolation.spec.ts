import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

type Audience = 'student' | 'family' | 'staff'
type PwaAudience = Exclude<Audience, 'staff'>

const gatewayOrigin = 'http://127.0.0.1:5380'
const audiences: Audience[] = ['student', 'family', 'staff']
const pwaAudiences: PwaAudience[] = ['student', 'family']
const websocketPersona = {
  student: AUTH_PERSONAS.student,
  family: AUTH_PERSONAS.family,
  staff: AUTH_PERSONAS.teacher,
} as const

interface RealtimeProbeRecord {
  url: string
  receivedTypes: string[]
  closeCode: number | null
}

async function installProductRealtimeProbe(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const NativeWebSocket = window.WebSocket
    const sockets: WebSocket[] = []
    const records: Array<{
      url: string
      receivedTypes: string[]
      closeCode: number | null
    }> = []

    function TrackedWebSocket(url: string | URL, protocols?: string | string[]): WebSocket {
      const socket =
        protocols === undefined ? new NativeWebSocket(url) : new NativeWebSocket(url, protocols)
      const record = {
        url: String(url),
        receivedTypes: [] as string[],
        closeCode: null as number | null,
      }
      sockets.push(socket)
      records.push(record)
      socket.addEventListener('message', (event) => {
        if (typeof event.data !== 'string') return
        try {
          const payload = JSON.parse(event.data) as { type?: unknown }
          if (typeof payload.type === 'string') record.receivedTypes.push(payload.type)
        } catch {
          record.receivedTypes.push('invalid-json')
        }
      })
      socket.addEventListener('close', (event) => {
        record.closeCode = event.code
      })
      return socket
    }

    Object.defineProperties(TrackedWebSocket, {
      CONNECTING: { value: NativeWebSocket.CONNECTING },
      OPEN: { value: NativeWebSocket.OPEN },
      CLOSING: { value: NativeWebSocket.CLOSING },
      CLOSED: { value: NativeWebSocket.CLOSED },
      prototype: { value: NativeWebSocket.prototype },
    })
    Object.defineProperty(window, 'WebSocket', {
      configurable: true,
      value: TrackedWebSocket,
      writable: true,
    })
    Object.defineProperty(window, '__vmshRealtimeProbe', {
      configurable: true,
      value: {
        closeLatest: () => sockets.at(-1)?.close(4001, 'E2E reconnect proof'),
        snapshot: () =>
          records.map((record) => ({ ...record, receivedTypes: [...record.receivedTypes] })),
      },
    })
  })
}

async function productRealtimeSnapshot(page: Page): Promise<RealtimeProbeRecord[]> {
  return page.evaluate(() => {
    const probe = (
      window as typeof window & {
        __vmshRealtimeProbe?: { snapshot(): RealtimeProbeRecord[] }
      }
    ).__vmshRealtimeProbe
    if (!probe) throw new Error('Product realtime probe was not installed')
    return probe.snapshot()
  })
}

async function closeLatestProductRealtimeSocket(page: Page): Promise<void> {
  await page.evaluate(() => {
    const probe = (
      window as typeof window & {
        __vmshRealtimeProbe?: { closeLatest(): void }
      }
    ).__vmshRealtimeProbe
    if (!probe) throw new Error('Product realtime probe was not installed')
    probe.closeLatest()
  })
}

const manifests = {
  student: {
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
  family: {
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
} as const

async function supportsServiceWorkers(page: Page): Promise<boolean> {
  return page.evaluate(() => window.isSecureContext && 'serviceWorker' in navigator)
}

async function waitForActiveWorker(page: Page, audience: PwaAudience): Promise<void> {
  const expectedScope = `${gatewayOrigin}/${audience}/`
  const expectedScript = `${gatewayOrigin}/${audience}/sw.js`
  await expect
    .poll(
      () =>
        page.evaluate(
          async ({ expectedScope }) => {
            const registrations = await navigator.serviceWorker.getRegistrations()
            const registration = registrations.find((item) => item.scope === expectedScope)
            return {
              scope: registration?.scope ?? null,
              script: registration?.active?.scriptURL ?? null,
              state: registration?.active?.state ?? null,
            }
          },
          { expectedScope },
        ),
      { timeout: 20_000 },
    )
    .toEqual({ scope: expectedScope, script: expectedScript, state: 'activated' })
}

async function ensureControlled(page: Page, audience: PwaAudience): Promise<void> {
  await waitForActiveWorker(page, audience)
  const expectedScript = `${gatewayOrigin}/${audience}/sw.js`
  if ((await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null)) === null) {
    await page.reload()
  }
  await expect
    .poll(() => page.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null))
    .toBe(expectedScript)
}

async function activeWorkerGeneration(page: Page): Promise<string> {
  return page.evaluate(
    () =>
      new Promise<string>((resolve, reject) => {
        const controller = navigator.serviceWorker.controller
        if (!controller) {
          reject(new Error('The page has no active Service Worker controller'))
          return
        }
        const nonce = crypto.randomUUID()
        const timeout = window.setTimeout(() => {
          navigator.serviceWorker.removeEventListener('message', onMessage)
          reject(new Error('Service Worker generation probe timed out'))
        }, 2_000)
        function onMessage(event: MessageEvent<unknown>) {
          if (
            typeof event.data !== 'object' ||
            event.data === null ||
            !('type' in event.data) ||
            event.data.type !== 'VMSH_E2E_GENERATION' ||
            !('nonce' in event.data) ||
            event.data.nonce !== nonce ||
            !('generation' in event.data) ||
            typeof event.data.generation !== 'string'
          ) {
            return
          }
          window.clearTimeout(timeout)
          navigator.serviceWorker.removeEventListener('message', onMessage)
          resolve(event.data.generation)
        }
        navigator.serviceWorker.addEventListener('message', onMessage)
        controller.postMessage({ type: 'VMSH_E2E_PROBE_GENERATION', nonce })
      }),
  )
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

for (const audience of audiences) {
  test(`${audience}: exact health and runtime contracts cross the one-origin gateway`, async ({
    request,
  }) => {
    const runtimeRequestId = `playwright.${audience}.runtime`
    const runtimeResponse = await request.get(`/${audience}/api/v1/runtime`, {
      headers: { 'X-Request-ID': runtimeRequestId },
    })
    expect(runtimeResponse.status()).toBe(200)
    expect(runtimeResponse.headers()['cache-control']).toBe('no-store')
    expect(runtimeResponse.headers()['x-request-id']).toBe(runtimeRequestId)
    expect(runtimeResponse.headers()['content-type']).toContain('application/json')
    const runtime = (await runtimeResponse.json()) as Record<string, unknown>
    expect(Object.keys(runtime).sort()).toEqual(
      [
        'apiBase',
        'appBase',
        'audience',
        'contractVersion',
        'features',
        'instance',
        'requestId',
        'serverTime',
        'websocketPath',
      ].sort(),
    )
    expect(runtime).toEqual({
      contractVersion: 1,
      audience,
      appBase: `/${audience}`,
      apiBase: `/${audience}/api/v1`,
      websocketPath: `/${audience}/ws`,
      instance: 'e2e',
      serverTime: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/),
      requestId: runtimeRequestId,
      features: {
        telegram: false,
        google: false,
        nats: false,
        prototype: true,
      },
    })

    const healthRequestId = `playwright.${audience}.health`
    const healthResponse = await request.get(`/${audience}/api/v1/health`, {
      headers: { 'X-Request-ID': healthRequestId },
    })
    expect(healthResponse.status()).toBe(200)
    expect(healthResponse.headers()['cache-control']).toBe('no-store')
    expect(healthResponse.headers()['x-request-id']).toBe(healthRequestId)
    expect(await healthResponse.json()).toEqual({
      ok: true,
      audience,
      requestId: healthRequestId,
    })
  })

  test(`${audience}: history fallback cannot swallow API, WS or missing assets`, async ({
    request,
  }) => {
    const deepLink = await request.get(`/${audience}/a/deep/application/route`, {
      headers: { Accept: 'text/html' },
    })
    expect(deepLink.status()).toBe(200)
    expect(deepLink.headers()['content-type']).toContain('text/html')
    expect(await deepLink.text()).toContain('<div id="root"></div>')

    const missingApi = await request.get(`/${audience}/api/v1/not-a-real-endpoint`, {
      headers: { Accept: 'text/html', 'X-Request-ID': `missing.${audience}` },
    })
    expect(missingApi.status()).toBe(404)
    expect(missingApi.headers()['content-type']).toContain('application/json')
    expect(missingApi.headers()['cache-control']).toBe('no-store')
    expect(await missingApi.text()).not.toContain('<div id="root"></div>')

    const malformedWebsocket = await request.get(`/${audience}/ws/not-exact`, {
      headers: { Accept: 'text/html' },
    })
    expect(malformedWebsocket.status()).toBe(404)
    expect(await malformedWebsocket.text()).not.toContain('<div id="root"></div>')

    const missingAsset = await request.get(`/${audience}/assets/not-built.js`, {
      headers: { Accept: 'text/html' },
    })
    expect(missingAsset.status()).toBe(404)
    expect(await missingAsset.text()).not.toContain('<div id="root"></div>')
  })
}

test('the gateway exposes no MSW artifact', async ({ request }) => {
  for (const path of [
    '/mockServiceWorker.js',
    ...audiences.map((audience) => `/${audience}/mockServiceWorker.js`),
  ]) {
    const response = await request.get(path)
    expect(response.status(), path).toBe(404)
  }
})

test('browser HTTP and WebSocket traffic cannot leave the E2E loopback origin', async ({
  page,
  networkGuard,
}) => {
  const externalHttpUrl = 'https://network-probe.example.invalid/e2e-fetch'
  const externalWebSocketUrl = 'wss://network-probe.example.invalid/e2e-websocket'
  networkGuard.expectBlocked(externalHttpUrl)
  networkGuard.expectBlocked(externalWebSocketUrl)

  await page.goto('/staff/')
  const fetchResult = await page.evaluate(async (rawUrl) => {
    try {
      await fetch(rawUrl)
      return 'unexpectedly-resolved'
    } catch {
      return 'blocked'
    }
  }, externalHttpUrl)
  expect(fetchResult).toBe('blocked')

  const websocketResult = await page.evaluate(
    (rawUrl) =>
      new Promise<'blocked' | 'unexpectedly-opened'>((resolve) => {
        const socket = new WebSocket(rawUrl)
        const timeout = window.setTimeout(() => {
          socket.close()
          resolve('blocked')
        }, 2_000)
        socket.onopen = () => {
          window.clearTimeout(timeout)
          socket.close()
          resolve('unexpectedly-opened')
        }
        socket.onerror = () => {
          window.clearTimeout(timeout)
          resolve('blocked')
        }
        socket.onclose = () => {
          window.clearTimeout(timeout)
          resolve('blocked')
        }
      }),
    externalWebSocketUrl,
  )
  expect(websocketResult).toBe('blocked')
})

for (const audience of pwaAudiences) {
  test(`${audience}: manifest and every icon have exact install boundaries`, async ({ request }) => {
    // Install boundaries are HTTP contracts. Checking the shell through the
    // request context avoids an unrelated WebKit PWA cold-start timeout.
    const shellResponse = await request.get(`/${audience}/`)
    expect(shellResponse.status()).toBe(200)
    expect(await shellResponse.text()).toContain(`href="/${audience}/manifest.webmanifest"`)
    const response = await request.get(`/${audience}/manifest.webmanifest`)
    expect(response.status()).toBe(200)
    expect(response.headers()['content-type']).toMatch(/application\/(manifest\+json|json)/)
    expect(await response.json()).toEqual(manifests[audience])
    for (const icon of manifests[audience].icons) {
      const iconResponse = await request.get(icon.src)
      expect(iconResponse.status(), icon.src).toBe(200)
      expect(iconResponse.headers()['content-type'], icon.src).toContain(icon.type)
      expect((await iconResponse.body()).byteLength, icon.src).toBeGreaterThan(0)
    }

    const workerResponse = await request.get(`/${audience}/sw.js`)
    expect(workerResponse.status()).toBe(200)
    expect(workerResponse.headers()['service-worker-allowed']).toBe(`/${audience}/`)
    expect(workerResponse.headers()['cache-control']).toBe('no-store')
  })
}

test('student and family service workers install, activate and control only their scopes', async ({
  page,
}) => {
  // One sequential browser context avoids a WebKit cold-context deadlock seen
  // only under the complete three-engine matrix. Every product assertion stays
  // audience-specific, including navigation control and negative boundaries.
  await page.goto('/__e2e__/health')
  test.skip(!(await supportsServiceWorkers(page)), 'This browser build has no Service Worker API')
  for (const audience of pwaAudiences) {
    await page.evaluate(
      async ({ audience }) => {
        await navigator.serviceWorker.register(`/${audience}/sw.js`, {
          scope: `/${audience}/`,
        })
      },
      { audience },
    )
    await waitForActiveWorker(page, audience)
  }

  const registrations = await page.evaluate(async () =>
    (await navigator.serviceWorker.getRegistrations())
      .map((registration) => ({
        scope: registration.scope,
        script: registration.active?.scriptURL ?? null,
      }))
      .sort((left, right) => left.scope.localeCompare(right.scope)),
  )
  expect(registrations).toEqual(
    [...pwaAudiences].sort().map((audience) => ({
      scope: `${gatewayOrigin}/${audience}/`,
      script: `${gatewayOrigin}/${audience}/sw.js`,
    })),
  )

  const navigationProbe = await page.context().newPage()
  for (const audience of pwaAudiences) {
    await navigationProbe.goto(`/${audience}/`, { waitUntil: 'domcontentloaded' })
    await expect
      .poll(() =>
        navigationProbe.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null),
      )
      .toBe(`${gatewayOrigin}/${audience}/sw.js`)
    // The anonymous product shell redirects to login after it becomes
    // controlled. Wait for that router navigation before probing unrelated
    // 404 documents, otherwise WebKit can cancel the first probe mid-flight.
    await expect(navigationProbe).toHaveURL(`/${audience}/login?returnTo=%2F`)
    for (const path of [
      `/${audience}/api`,
      `/${audience}/ws/not-exact`,
      `/${audience}/assets/not-built.js`,
      `/${audience}/not-built.js`,
      `/${audience}/missing-document.html`,
      `/${audience}/missing-print.pdf`,
      `/${audience}/robots.txt`,
    ]) {
      const response = await navigationProbe.goto(path)
      expect(response?.status(), path).toBe(404)
      expect(await navigationProbe.locator('#root').count(), path).toBe(0)
    }
  }
  await navigationProbe.close()
})

test('student and family workers own disjoint scopes and Cache Storage', async ({ page }) => {
  await page.goto('/student/')
  test.skip(!(await supportsServiceWorkers(page)), 'This browser build has no Service Worker API')
  await ensureControlled(page, 'student')
  await page.goto('/family/')
  await ensureControlled(page, 'family')

  const state = await page.evaluate(async () => {
    await Promise.all([
      fetch('/student/api/v1/runtime'),
      fetch('/student/api/v1/auth/session'),
      fetch('/family/api/v1/health'),
      fetch('/family/api/v1/auth/session'),
    ])
    const registrations = (await navigator.serviceWorker.getRegistrations())
      .map((registration) => registration.scope)
      .sort()
    const cacheEntries = await Promise.all(
      (await caches.keys()).map(async (name) => {
        const cache = await caches.open(name)
        return {
          name,
          urls: (await cache.keys()).map((request) => request.url).sort(),
        }
      }),
    )
    return { registrations, cacheEntries }
  })

  expect(state.registrations).toEqual([`${gatewayOrigin}/family/`, `${gatewayOrigin}/student/`])
  const studentCaches = state.cacheEntries
    .filter((cache) => cache.urls.some((url) => new URL(url).pathname.startsWith('/student/')))
    .map((cache) => cache.name)
  const familyCaches = state.cacheEntries
    .filter((cache) => cache.urls.some((url) => new URL(url).pathname.startsWith('/family/')))
    .map((cache) => cache.name)
  expect(studentCaches.length).toBeGreaterThan(0)
  expect(familyCaches.length).toBeGreaterThan(0)
  expect(studentCaches).toContain(`vmsh-179-student-precache-${gatewayOrigin}/student/v1`)
  expect(familyCaches).toContain(`vmsh-179-family-precache-${gatewayOrigin}/family/v1`)
  expect(studentCaches.filter((name) => familyCaches.includes(name))).toEqual([])
  for (const cache of state.cacheEntries) {
    expect(
      cache.urls.every((url) => !new URL(url).pathname.includes('/api/')),
      cache.name,
    ).toBe(true)
    expect(
      cache.urls.every((url) => !new URL(url).pathname.includes('/auth/')),
      cache.name,
    ).toBe(true)
  }

  await page.goto('/staff/')
  expect(await page.evaluate(() => navigator.serviceWorker.controller)).toBeNull()
  expect(
    await page.evaluate(
      async () => (await navigator.serviceWorker.getRegistration('/staff/'))?.scope ?? null,
    ),
  ).toBeNull()
})

for (const audience of pwaAudiences) {
  test(`${audience}: a byte-different built worker reaches prompt and controls the page`, async ({
    page,
  }) => {
    test.setTimeout(45_000)
    await page.goto(`/${audience}/`)
    test.skip(!(await supportsServiceWorkers(page)), 'This browser build has no Service Worker API')
    await ensureControlled(page, audience)
    expect(await activeWorkerGeneration(page)).toBe('baseline')
    const obsoleteCacheName = `vmsh-179-${audience}-precache-${gatewayOrigin}/${audience}/v0`
    const legacyUnscopedCacheName = `vmsh-179-${audience}-precache-v1`
    const legacyRecentMediaCacheName = `vmsh-${audience}-recent-media-v1`
    const otherAudience = audience === 'student' ? 'family' : 'student'
    const otherAudienceSentinel = `vmsh-179-${otherAudience}-precache-v1`
    const otherAudienceRecentMediaSentinel = `vmsh-${otherAudience}-recent-media-v1`
    await page.evaluate(
      async (cacheNames) => {
        for (const cacheName of cacheNames) {
          const cache = await caches.open(cacheName)
          await cache.put('/obsolete-phase-0-entry', new Response('obsolete'))
        }
      },
      [
        obsoleteCacheName,
        legacyUnscopedCacheName,
        legacyRecentMediaCacheName,
        otherAudienceSentinel,
        otherAudienceRecentMediaSentinel,
      ],
    )
    expect(await page.evaluate((cacheName) => caches.has(cacheName), obsoleteCacheName)).toBe(true)
    expect(
      await page.evaluate((cacheName) => caches.has(cacheName), legacyRecentMediaCacheName),
    ).toBe(true)
    expect(
      await page.evaluate((cacheName) => caches.has(cacheName), otherAudienceRecentMediaSentinel),
    ).toBe(true)

    const initialPrompt = page.getByTestId('pwa-update-state')
    if (await initialPrompt.isVisible()) {
      const dismiss = initialPrompt.getByRole('button', { name: /Скрыть|Закрыть/ })
      await dismiss.click()
    }
    const controlToken = process.env.VMSH_E2E_GATEWAY_CONTROL_TOKEN
    expect(controlToken).toBeTruthy()
    const generation = `pw-${test.info().project.name}-${Date.now()}`.toLowerCase()
    const controlResult = await page.evaluate(
      async ({ audience, controlToken, generation }) => {
        const response = await fetch(`/__e2e__/service-worker-generation/${audience}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-VMSH-E2E-Control': controlToken,
          },
          body: JSON.stringify({ generation }),
        })
        const payload: unknown = await response.json()
        return { status: response.status, payload }
      },
      { audience, controlToken: controlToken!, generation },
    )
    expect(controlResult).toEqual({
      status: 200,
      payload: { ok: true, audience, generation },
    })

    const runtimeModeResult = await page.evaluate(
      async ({ audience, controlToken }) => {
        const response = await fetch(`/__e2e__/runtime-mode/${audience}`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-VMSH-E2E-Control': controlToken,
          },
          body: JSON.stringify({ mode: 'incompatible' }),
        })
        const payload: unknown = await response.json()
        return { status: response.status, payload }
      },
      { audience, controlToken: controlToken! },
    )
    expect(runtimeModeResult).toEqual({
      status: 200,
      payload: { ok: true, audience, mode: 'incompatible' },
    })

    await page.reload()
    await expect(page.getByRole('alert')).toContainText('Не удалось безопасно открыть кабинет')

    await page.evaluate(async (expectedScope) => {
      const registration = (await navigator.serviceWorker.getRegistrations()).find(
        (item) => item.scope === expectedScope,
      )
      if (!registration) throw new Error(`Missing registration for ${expectedScope}`)
      await registration.update()
    }, `${gatewayOrigin}/${audience}/`)
    await expect(page.getByText('Доступно обновление.')).toBeVisible({
      timeout: 20_000,
    })
    await expect
      .poll(() =>
        page.evaluate(async (expectedScope) => {
          const registration = (await navigator.serviceWorker.getRegistrations()).find(
            (item) => item.scope === expectedScope,
          )
          return registration?.waiting?.state ?? null
        }, `${gatewayOrigin}/${audience}/`),
      )
      .toBe('installed')
    // The product reloads exactly once after the replacement worker really
    // becomes this document's controller. Arm the observer before the click:
    // a test-side reload would hide whether the real update UX works.
    // Authentication may already have replaced the route with its audience-
    // local login URL while RuntimeBootstrap shows the incompatible-runtime
    // fallback. A reload must preserve that exact current URL, not force root.
    const currentUrl = page.url()
    const updateNavigation = page.waitForEvent('framenavigated', {
      predicate: (frame) => frame === page.mainFrame() && frame.url() === currentUrl,
      timeout: 30_000,
    })
    await Promise.all([
      updateNavigation,
      page.getByRole('button', { name: 'Обновить сейчас' }).click(),
    ])
    await page.waitForLoadState('domcontentloaded')
    await expect(page.getByRole('alert')).toContainText('Не удалось безопасно открыть кабинет')
    await expect
      .poll(
        async () => {
          try {
            return await activeWorkerGeneration(page)
          } catch {
            return null
          }
        },
        { timeout: 20_000 },
      )
      .toBe(generation)
    const readyRegistration = await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.ready
      return {
        scope: registration.scope,
        script: registration.active?.scriptURL ?? null,
      }
    })
    // WebKit can retain an `activating` state wrapper after `ready` resolves.
    // The ready registration plus a generation response from the page's
    // controller are the interoperable proof that the new worker owns it.
    expect(readyRegistration).toEqual({
      scope: `${gatewayOrigin}/${audience}/`,
      script: `${gatewayOrigin}/${audience}/sw.js`,
    })
    await expect
      .poll(() => page.evaluate((cacheName) => caches.has(cacheName), obsoleteCacheName))
      .toBe(false)
    await expect
      .poll(() => page.evaluate((cacheName) => caches.has(cacheName), legacyUnscopedCacheName))
      .toBe(false)
    await expect
      .poll(() => page.evaluate((cacheName) => caches.has(cacheName), legacyRecentMediaCacheName))
      .toBe(false)
    expect(await page.evaluate((cacheName) => caches.has(cacheName), otherAudienceSentinel)).toBe(
      true,
    )
    expect(
      await page.evaluate((cacheName) => caches.has(cacheName), otherAudienceRecentMediaSentinel),
    ).toBe(true)
  })
}

for (const audience of audiences) {
  test(`${audience}: product realtime reconnects with cursor and refetches HTTP authority`, async ({
    page,
  }) => {
    // This observes the socket created by RealtimeProvider in the production
    // bundle. Unit tests own timing edge cases; here real aiohttp proves the
    // browser composition and mandatory reconnect refetch from Phase 1.
    await installProductRealtimeProbe(page)
    let authMeRequests = 0
    page.on('request', (request) => {
      const url = new URL(request.url())
      if (request.method() === 'GET' && url.pathname === `/${audience}/api/v1/auth/me`) {
        authMeRequests += 1
      }
    })
    await loginThroughUi(page, websocketPersona[audience])
    await expect
      .poll(() => productRealtimeSnapshot(page))
      .toEqual([
        {
          url: `${gatewayOrigin.replace('http:', 'ws:')}/${audience}/ws`,
          // Other specs use the same real event fan-out. An owner-scoped
          // invalidation may legitimately arrive before this probe closes the
          // socket; connection establishment is the invariant under test.
          receivedTypes: expect.arrayContaining(['connected']),
          closeCode: null,
        },
      ])
    const authorityBaseline = authMeRequests

    await closeLatestProductRealtimeSocket(page)
    await expect
      .poll(() => productRealtimeSnapshot(page))
      .toEqual([
        {
          url: `${gatewayOrigin.replace('http:', 'ws:')}/${audience}/ws`,
          receivedTypes: expect.arrayContaining(['connected']),
          // Browser engines are allowed to report a clean 1000 close when a
          // local test abort races their network teardown. The proof here is
          // that the original product socket actually closed, not which
          // private code the harness managed to put on the wire.
          closeCode: expect.any(Number),
        },
        {
          url: expect.stringMatching(
            new RegExp(`^ws://127\\.0\\.0\\.1:5380/${audience}/ws\\?cursor=\\d+$`),
          ),
          // Other parallel product flows may publish valid invalidations after
          // reconnect. The required recovery signal must still be present.
          receivedTypes: expect.arrayContaining(['resync-required']),
          closeCode: null,
        },
      ])
    await expect.poll(() => authMeRequests).toBeGreaterThan(authorityBaseline)
    await expect(page.locator(`[data-product="${audience}"]`)).toBeVisible()
  })

  test(`${audience}: WebSocket first connect, heartbeat and reconnect require refetch`, async ({
    page,
  }) => {
    // Phase 1 made every audience WebSocket private. Keep this runtime proof on
    // the real login/session boundary instead of preserving the old anonymous
    // Phase-0 handshake. See development-plan/05-phase-1-auth.md.
    await loginThroughUi(page, websocketPersona[audience])
    const firstConnection = await page.evaluate(
      ({ audience }) =>
        new Promise<Array<Record<string, unknown>>>((resolve, reject) => {
          const url = new URL(`/${audience}/ws`, window.location.href)
          url.protocol = 'ws:'
          const socket = new WebSocket(url)
          const messages: Array<Record<string, unknown>> = []
          const timeout = window.setTimeout(() => reject(new Error('WebSocket timeout')), 10_000)
          socket.onerror = () => reject(new Error('WebSocket connection failed'))
          socket.onmessage = (message) => {
            const payload = JSON.parse(String(message.data)) as Record<string, unknown>
            messages.push(payload)
            if (payload.type === 'connected') socket.send(JSON.stringify({ type: 'ping' }))
            if (payload.type === 'pong') {
              window.clearTimeout(timeout)
              socket.close()
              resolve(messages)
            }
          }
        }),
      { audience },
    )
    const connectedIndex = firstConnection.findIndex((message) => message.type === 'connected')
    const pongIndex = firstConnection.findIndex((message) => message.type === 'pong')
    expect(connectedIndex).toBe(0)
    expect(pongIndex).toBeGreaterThan(connectedIndex)
    expect(firstConnection[connectedIndex]).toEqual({
      type: 'connected',
      cursor: expect.any(Number),
      serverTime: expect.any(String),
      audience,
    })
    expect(firstConnection[pongIndex]).toEqual({
      type: 'pong',
      cursor: expect.any(Number),
      serverTime: expect.any(String),
    })

    const reconnect = await page.evaluate(
      ({ audience }) =>
        new Promise<Record<string, unknown>>((resolve, reject) => {
          const url = new URL(`/${audience}/ws?cursor=999`, window.location.href)
          url.protocol = 'ws:'
          const socket = new WebSocket(url)
          const timeout = window.setTimeout(() => reject(new Error('WebSocket timeout')), 10_000)
          socket.onerror = () => reject(new Error('WebSocket connection failed'))
          socket.onmessage = (message) => {
            window.clearTimeout(timeout)
            socket.close()
            resolve(JSON.parse(String(message.data)) as Record<string, unknown>)
          }
        }),
      { audience },
    )
    expect(reconnect).toEqual({
      type: 'resync-required',
      cursor: expect.any(Number),
      serverTime: expect.any(String),
      reason: 'reconnect-full-refetch-required',
    })
  })
}

test('student: current-session revoke closes product realtime and returns to login', async ({
  page,
}) => {
  await installProductRealtimeProbe(page)
  await loginThroughUi(page, AUTH_PERSONAS.student)
  await expect.poll(() => productRealtimeSnapshot(page)).toHaveLength(1)
  await expect
    .poll(async () => (await productRealtimeSnapshot(page))[0]?.receivedTypes)
    // Full-matrix runs share the real fan-out, so unrelated owner-scoped
    // invalidations may arrive before this session is revoked.
    .toEqual(expect.arrayContaining(['connected']))

  const revokeStatus = await page.evaluate(async () => {
    const me = await fetch('/student/api/v1/auth/me', { credentials: 'include' })
    const context = (await me.json()) as { currentSession: { sessionId: string } }
    const response = await fetch(
      `/student/api/v1/auth/sessions/${encodeURIComponent(context.currentSession.sessionId)}`,
      { credentials: 'include', method: 'DELETE' },
    )
    return response.status
  })
  expect(revokeStatus).toBe(204)
  await expect(page).toHaveURL((url) => url.pathname === '/student/login')
  await expect
    .poll(async () => (await productRealtimeSnapshot(page)).map((record) => record.closeCode))
    // Playwright's pass-through WebSocketRoute currently normalizes the
    // server's 1008 to 1000 in all three engines. Unit and aiohttp integration
    // tests own the exact wire code; this browser proof owns close + HTTP
    // authority logout + absence of reconnect.
    .toEqual([expect.any(Number)])
  // An authority-sensitive close invokes one HTTP check and is never
  // interpreted as an endless transport reconnect after revocation.
  await page.waitForTimeout(1_000)
  expect(await productRealtimeSnapshot(page)).toHaveLength(1)
})

test('localStorage theme state stays audience-scoped on the shared origin', async ({ page }) => {
  const storageSnapshot = () =>
    page.evaluate(() => {
      const themePrefix = 'vmsh-179:v1:'
      const themeSuffix = ':e2e:theme'
      const authMarkerPrefix = 'vmshpwa:auth-refresh-complete:v1:'
      const runtimeCachePrefix = 'vmsh-179:runtime:v1:'
      const entries = Object.entries(localStorage).sort(([left], [right]) =>
        left.localeCompare(right),
      )
      return {
        themes: Object.fromEntries(
          entries.filter(([key]) => key.startsWith(themePrefix) && key.endsWith(themeSuffix)),
        ),
        authMarkers: Object.fromEntries(
          entries.filter(([key]) => key.startsWith(authMarkerPrefix)),
        ),
        runtimeCacheKeys: entries
          .map(([key]) => key)
          .filter((key) => key.startsWith(runtimeCachePrefix)),
        otherKeys: entries
          .map(([key]) => key)
          .filter(
            (key) =>
              !(key.startsWith(themePrefix) && key.endsWith(themeSuffix)) &&
              !key.startsWith(authMarkerPrefix) &&
              !key.startsWith(runtimeCachePrefix),
          ),
      }
    })

  await loginThroughUi(page, AUTH_PERSONAS.student)
  const studentTheme = page.getByRole('button', { name: 'Переключить на тёмную тему' })
  await expect(studentTheme).toBeVisible()
  await studentTheme.click()
  await expect(page.locator('html')).toHaveClass(/dark/)

  await loginThroughUi(page, AUTH_PERSONAS.family)
  await expect(page.getByRole('button', { name: 'Переключить на тёмную тему' })).toBeVisible()
  await expect(page.locator('html')).not.toHaveClass(/dark/)
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('vmsh-179:v1:family:e2e:theme')))
    .toBe('light')
  const initialStorage = await storageSnapshot()
  expect(initialStorage.themes).toEqual({
    'vmsh-179:v1:family:e2e:theme': 'light',
    'vmsh-179:v1:student:e2e:theme': 'dark',
  })
  expect(Object.keys(initialStorage.authMarkers).sort()).toEqual([
    'vmshpwa:auth-refresh-complete:v1:family',
    'vmshpwa:auth-refresh-complete:v1:student',
  ])
  expect(Object.values(initialStorage.authMarkers)).toEqual([
    expect.stringMatching(/^\d{13}$/),
    expect.stringMatching(/^\d{13}$/),
  ])
  expect(initialStorage.runtimeCacheKeys).toEqual([
    'vmsh-179:runtime:v1:family',
    'vmsh-179:runtime:v1:student',
  ])
  expect(initialStorage.otherKeys).toEqual([])

  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.goto('/student/')
  await expect(page.locator('html')).toHaveClass(/dark/)
  const finalStorage = await storageSnapshot()
  expect(finalStorage.themes).toEqual({
    'vmsh-179:v1:family:e2e:theme': 'dark',
    'vmsh-179:v1:student:e2e:theme': 'dark',
  })
  expect(Object.keys(finalStorage.authMarkers).sort()).toEqual([
    'vmshpwa:auth-refresh-complete:v1:family',
    'vmshpwa:auth-refresh-complete:v1:student',
  ])
  expect(Object.values(finalStorage.authMarkers)).toEqual([
    expect.stringMatching(/^\d{13}$/),
    expect.stringMatching(/^\d{13}$/),
  ])
  expect(finalStorage.runtimeCacheKeys).toEqual([
    'vmsh-179:runtime:v1:family',
    'vmsh-179:runtime:v1:student',
  ])
  expect(finalStorage.otherKeys).toEqual([])
})

test('runtime-created IndexedDB names encode audience and instance', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student)
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await loginThroughUi(page, AUTH_PERSONAS.family)
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await loginThroughUi(page, AUTH_PERSONAS.teacher)
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  const supportsEnumeration = await page.evaluate(() => typeof indexedDB.databases === 'function')
  test.skip(!supportsEnumeration, 'This browser cannot enumerate IndexedDB databases')
  const names = await page.evaluate(async () =>
    (await indexedDB.databases())
      .map((database) => database.name)
      .filter((name): name is string => typeof name === 'string')
      .sort(),
  )
  expect(names.filter((name) => name.startsWith('vmsh-179:'))).toEqual([
    'vmsh-179:v1:family:e2e',
    'vmsh-179:v1:student:e2e',
  ])
  expect(new Set(names).size).toBe(names.length)
})
