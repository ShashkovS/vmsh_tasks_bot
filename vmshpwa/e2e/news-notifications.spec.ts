import { AUTH_PERSONAS, loginThroughUi, type AuthPersona } from './auth-personas'
import { expect, test } from './fixtures'

const postText = 'Разбор задач — сегодня в 17:00.'
const postId = 'news.phase8.e2e'
const offlineMarker = 'vmsh-e2e-news-api-offline'

test.setTimeout(90_000)

function phase8Persona(project: string, audience: 'student' | 'family'): AuthPersona {
  if (audience === 'student') {
    return {
      persona: 'student',
      accountPublicId: `account-news-student-e2e-${project}`,
      audience,
      username: `news-student-e2e-${project}`,
      credentialField: 'telegramToken',
      credential: AUTH_PERSONAS.student.credential,
    }
  }
  return {
    persona: 'family',
    accountPublicId: `account-news-family-e2e-${project}`,
    audience,
    username: `news-family-e2e-${project}`,
    credentialField: 'password',
    credential: AUTH_PERSONAS.family.credential,
  }
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

test('Phase 8: Student reads cached news, dismisses a banner and acknowledges the event', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, phase8Persona(testInfo.project.name, 'student'), '/student/')

  const banner = page.locator('[data-banner-id="banner.phase8.e2e"]')
  await expect(banner).toContainText('Разбор сегодня в 17:00')
  await banner.getByRole('button', { name: 'Скрыть объявление' }).click()
  await expect(banner).toHaveCount(0)
  await page.reload()
  await expect(page.locator('[data-banner-id="banner.phase8.e2e"]')).toHaveCount(0)

  await page.goto('/student/news')
  await expect(page.getByText(postText, { exact: false })).toBeVisible()
  await expect(page.getByText('Тестовый канал ВМШ')).toBeVisible()
  await page.getByRole('link', { name: 'Открыть публикацию' }).click()
  await expect(page).toHaveURL(`/student/news/${postId}`)
  await expect(page.getByText(postText, { exact: false })).toBeVisible()

  // The production Service Worker supplies the shell; rejecting only Student
  // API fetches forces the page to prove its account-scoped IndexedDB fallback.
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null)
  await page.addInitScript((marker) => {
    const nativeFetch = window.fetch.bind(window)
    window.fetch = (input, init) => {
      const rawUrl = typeof input === 'string' || input instanceof URL ? String(input) : input.url
      const url = new URL(rawUrl, window.location.href)
      if (
        window.sessionStorage.getItem(marker) === '1' &&
        url.pathname.startsWith('/student/api/')
      ) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return nativeFetch(input, init)
    }
  }, offlineMarker)
  await page.evaluate((marker) => window.sessionStorage.setItem(marker, '1'), offlineMarker)
  try {
    await page.reload()
    await expect(page.getByText(postText, { exact: false })).toBeVisible()
  } finally {
    await page.evaluate((marker) => window.sessionStorage.removeItem(marker), offlineMarker)
  }

  await page.goto('/student/profile/notifications')
  const eventBeforeRead = await page.evaluate(async () => {
    const response = await fetch('/student/api/v1/notification-events?unreadOnly=false')
    return (await response.json()) as {
      items: Array<{ eventId: string; readAt: string | null }>
    }
  })
  const targetEvent = eventBeforeRead.items.find(
    (item) => item.eventId === `notification.news.phase8.e2e.student.${testInfo.project.name}`,
  )
  expect(targetEvent).toBeDefined()
  const event = page.getByRole('link', { name: /Новая публикация/ })
  await expect(event).toBeVisible()
  if (targetEvent?.readAt === null) {
    // The visibility observer may acknowledge the item between rendering the
    // badge and arming a response listener. Poll the authoritative API instead:
    // this also remains valid when a Playwright retry sees the completed write.
    // Reading requires an actually foreground document. Full-matrix Playwright
    // runs create background pages, unlike the single active browser tab a
    // student uses, so explicitly foreground this page before starting the
    // product's three-second visibility window.
    await page.bringToFront()
    await expect.poll(() => page.evaluate(() => document.visibilityState)).toBe('visible')
    await event.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    await expect(event).toBeInViewport({ ratio: 0.75 })
    await expect
      .poll(
        async () => {
          const response = await page.evaluate(async () => {
            const result = await fetch('/student/api/v1/notification-events?unreadOnly=false')
            return (await result.json()) as {
              items: Array<{ eventId: string; readAt: string | null }>
            }
          })
          return response.items.find(
            (item) =>
              item.eventId === `notification.news.phase8.e2e.student.${testInfo.project.name}`,
          )?.readAt
        },
        { timeout: 15_000 },
      )
      .toEqual(expect.any(String))
  }
  await expect(event.getByText('Новое', { exact: true })).toHaveCount(0)
  const unreadNews = await page.evaluate(async () => {
    const response = await fetch('/student/api/v1/notification-events?unreadOnly=true')
    return (await response.json()) as { items: Array<{ category: string }> }
  })
  expect(unreadNews.items.some((item) => item.category === 'news')).toBe(false)

  const pushCapability = await page.evaluate(() => ({
    supported:
      typeof Notification !== 'undefined' &&
      'serviceWorker' in navigator &&
      typeof PushManager !== 'undefined',
    permission: typeof Notification === 'undefined' ? 'unavailable' : Notification.permission,
  }))
  if (!pushCapability.supported) {
    await expect(page.getByText('Push не поддерживаются')).toBeVisible()
  } else if (pushCapability.permission === 'denied') {
    await expect(page.getByText('Push запрещены в браузере')).toBeVisible()
  } else {
    const deviceSection = page
      .getByRole('heading', { name: 'На этом устройстве' })
      .locator('xpath=ancestor::section[1]')
    await expect(deviceSection).toContainText(
      /Включить уведомления|Push включены на этом устройстве|Не удалось настроить push/,
    )
  }
})

test('Phase 8: Family sees the shared post, banner and its own news event', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, phase8Persona(testInfo.project.name, 'family'), '/family/')
  await expect(page.locator('[data-banner-id="banner.phase8.e2e"]')).toContainText(
    'Разбор сегодня в 17:00',
  )
  await page.goto('/family/news')
  await expect(page.getByText(postText, { exact: false })).toBeVisible()
  await page.getByRole('link', { name: 'Открыть публикацию' }).click()
  await expect(page).toHaveURL(`/family/news/${postId}`)
  await expect(page.getByText(postText, { exact: false })).toBeVisible()

  const notifications = await page.evaluate(async () => {
    const response = await fetch('/family/api/v1/notification-events?unreadOnly=true')
    return {
      status: response.status,
      payload: (await response.json()) as { items: Array<{ category: string; route: string }> },
    }
  })
  expect(notifications.status).toBe(200)
  expect(notifications.payload.items).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ category: 'news', route: `/family/news/${postId}` }),
    ]),
  )
})
