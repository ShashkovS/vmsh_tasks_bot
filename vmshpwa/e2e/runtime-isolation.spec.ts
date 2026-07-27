import { expect, test, type Page } from './fixtures'

type Audience = 'student' | 'family' | 'staff'
type PwaAudience = Exclude<Audience, 'staff'>

const gatewayOrigin = 'http://127.0.0.1:5380'
const audiences: Audience[] = ['student', 'family', 'staff']
const pwaAudiences: PwaAudience[] = ['student', 'family']

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
  test(`${audience}: manifest and every icon have exact install boundaries`, async ({
    page,
    request,
  }) => {
    await page.goto(`/${audience}/`)
    await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
      'href',
      `/${audience}/manifest.webmanifest`,
    )
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

  test(`${audience}: exact service-worker scope installs and activates`, async ({ page }) => {
    await page.goto(`/${audience}/`)
    test.skip(!(await supportsServiceWorkers(page)), 'This browser build has no Service Worker API')
    await ensureControlled(page, audience)

    const registrations = await page.evaluate(async () =>
      (await navigator.serviceWorker.getRegistrations()).map((registration) => ({
        scope: registration.scope,
        script: registration.active?.scriptURL ?? null,
      })),
    )
    expect(registrations).toEqual([
      {
        scope: `${gatewayOrigin}/${audience}/`,
        script: `${gatewayOrigin}/${audience}/sw.js`,
      },
    ])

    const navigationProbe = await page.context().newPage()
    await navigationProbe.goto(`/${audience}/`)
    await expect
      .poll(() =>
        navigationProbe.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null),
      )
      .toBe(`${gatewayOrigin}/${audience}/sw.js`)
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
    await navigationProbe.close()
  })
}

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
      await initialPrompt.getByRole('button', { name: 'Закрыть' }).click()
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
    await expect(page.getByText('Доступно обновление приложения')).toBeVisible({
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
    // vite-plugin-pwa/Workbox owns the reload after SKIP_WAITING. Arm the
    // observer before the click: an additional explicit reload races that
    // navigation in Firefox and hides whether the real update UX works.
    const updateNavigation = page.waitForEvent('framenavigated', {
      predicate: (frame) =>
        frame === page.mainFrame() && frame.url() === `${gatewayOrigin}/${audience}/`,
      timeout: 30_000,
    })
    await Promise.all([updateNavigation, page.getByRole('button', { name: 'Обновить' }).click()])
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
  test(`${audience}: WebSocket first connect, heartbeat and reconnect require refetch`, async ({
    page,
  }) => {
    await page.goto(`/${audience}/`)
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
    expect(firstConnection).toHaveLength(2)
    expect(firstConnection[0]).toEqual({
      type: 'connected',
      cursor: expect.any(Number),
      serverTime: expect.any(String),
      audience,
    })
    expect(firstConnection[1]).toEqual({
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

test('localStorage theme state stays audience-scoped on the shared origin', async ({ page }) => {
  await page.goto('/student/')
  const studentTheme = page.getByRole('button', { name: 'Переключить на тёмную тему' })
  await expect(studentTheme).toBeVisible()
  await studentTheme.click()
  await expect(page.locator('html')).toHaveClass(/dark/)

  await page.goto('/family/')
  await expect(page.getByRole('button', { name: 'Переключить на тёмную тему' })).toBeVisible()
  await expect(page.locator('html')).not.toHaveClass(/dark/)
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem('vmsh-179:v1:family:e2e:theme')))
    .toBe('light')
  expect(
    await page.evaluate(() => ({
      student: localStorage.getItem('vmsh-179:v1:student:e2e:theme'),
      family: localStorage.getItem('vmsh-179:v1:family:e2e:theme'),
      keys: Object.keys(localStorage).sort(),
    })),
  ).toEqual({
    student: 'dark',
    family: 'light',
    keys: ['vmsh-179:v1:family:e2e:theme', 'vmsh-179:v1:student:e2e:theme'],
  })

  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.goto('/student/')
  await expect(page.locator('html')).toHaveClass(/dark/)
  expect(
    await page.evaluate(() => ({
      student: localStorage.getItem('vmsh-179:v1:student:e2e:theme'),
      family: localStorage.getItem('vmsh-179:v1:family:e2e:theme'),
      keys: Object.keys(localStorage).sort(),
    })),
  ).toEqual({
    student: 'dark',
    family: 'dark',
    keys: ['vmsh-179:v1:family:e2e:theme', 'vmsh-179:v1:student:e2e:theme'],
  })
})

test('runtime-created IndexedDB names encode audience and instance', async ({ page }) => {
  await page.goto('/student/')
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await page.goto('/family/')
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await page.goto('/staff/')
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
