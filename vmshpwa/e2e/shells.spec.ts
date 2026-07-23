import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

const apps = [
  {
    audience: 'student',
    origin: 'http://127.0.0.1:5373',
    title: 'ВМШ 179',
    detail: '/student/tasks/geometry-7',
  },
  {
    audience: 'family',
    origin: 'http://127.0.0.1:5374',
    title: 'ВМШ 179',
    detail: '/family/children/masha',
  },
  {
    audience: 'staff',
    origin: 'http://127.0.0.1:5375',
    title: 'ВМШ 179',
    detail: '/staff/review/submission-17',
  },
] as const

for (const app of apps) {
  test(`${app.audience}: shell, base path and history fallback`, async ({ page }) => {
    await page.goto(`${app.origin}/${app.audience}/`)
    await expect(page.getByRole('link', { name: app.title }).first()).toBeVisible()
    await expect(page.locator('[data-product]')).toHaveAttribute('data-product', app.audience)

    await page.goto(`${app.origin}${app.detail}`)
    await expect(page.locator('main')).toBeVisible()
    await expect(page.getByText('Страница не найдена')).toHaveCount(0)
  })

  test(`${app.audience}: runtime contract and audience isolation`, async ({ request }) => {
    const response = await request.get(`${app.origin}/${app.audience}/api/v1/runtime`)
    expect(response.ok()).toBeTruthy()
    const runtime: unknown = await response.json()
    expect(runtime).toMatchObject({
      audience: app.audience,
      appBase: `/${app.audience}`,
      apiBase: `/${app.audience}/api/v1`,
      websocketPath: `/${app.audience}/ws`,
      instance: 'e2e',
      features: { telegram: false, google: false, prototype: true },
    })
  })
}

test('theme choice survives navigation within its application', async ({ page }) => {
  await page.goto('http://127.0.0.1:5373/student/')
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/dark/)
})

test('websocket reconnect cursor requests an explicit resync', async ({ page }) => {
  await page.goto('http://127.0.0.1:5373/student/')
  const event = await page.evaluate(
    () =>
      new Promise<Record<string, unknown>>((resolve, reject) => {
        const url = new URL('/student/ws?cursor=999', window.location.href)
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        const websocket = new WebSocket(url)
        websocket.onerror = () => reject(new Error('websocket connection failed'))
        websocket.onmessage = (message) => {
          const payload: unknown = JSON.parse(String(message.data))
          if (typeof payload !== 'object' || payload === null) {
            reject(new Error('websocket event must be an object'))
            return
          }
          resolve(payload as Record<string, unknown>)
          websocket.close()
        }
      }),
  )
  expect(event.type).toBe('resync-required')
  expect(event.reason).toBe('client-cursor-is-ahead')
})

for (const app of apps.slice(0, 2)) {
  test(`${app.audience}: install metadata and service-worker update channel`, async ({ page }) => {
    await page.goto(`${app.origin}/${app.audience}/`)
    const manifestHref = await page.locator('link[rel="manifest"]').getAttribute('href')
    expect(manifestHref).toContain(`/${app.audience}/`)
    await expect
      .poll(
        async () => {
          try {
            return await page.evaluate(async () => {
              const ready = navigator.serviceWorker?.ready
              if (ready === undefined) return null
              const registration = await Promise.race([
                ready,
                new Promise<null>((resolve) => setTimeout(() => resolve(null), 2_000)),
              ])
              if (!registration) return null
              await registration.update()
              return {
                scope: registration.scope,
                hasWorker: Boolean(
                  registration.active || registration.installing || registration.waiting,
                ),
                updateAccepted: true,
              }
            })
          } catch {
            // The first dev-worker activation may replace the browsing context.
            // Poll again against the newly controlled page instead of treating it
            // as an application failure.
            return null
          }
        },
        { timeout: 15_000 },
      )
      .toMatchObject({
        scope: expect.stringContaining(`/${app.audience}/`),
        hasWorker: true,
        updateAccepted: true,
      })
  })
}

test('@visual student current week', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('http://127.0.0.1:5373/student/')
  const updateState = page.getByTestId('pwa-update-state')
  await updateState.waitFor({ state: 'visible', timeout: 2_000 }).catch(() => undefined)
  if (await updateState.isVisible())
    await updateState.getByRole('button', { name: 'Закрыть' }).click()
  await expect(page).toHaveScreenshot('student-current-week.png', { fullPage: true })
})

test('@visual staff weekly dashboard', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('http://127.0.0.1:5375/staff/')
  await expect(page).toHaveScreenshot('staff-weekly-dashboard.png', { fullPage: true })
})
