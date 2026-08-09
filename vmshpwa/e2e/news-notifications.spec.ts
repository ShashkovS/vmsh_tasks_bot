import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }

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

function digestTarget(project: string) {
  const target = contentFixture.targets.find((candidate) => candidate.project === project)
  if (!target) throw new Error(`No Family digest target for Playwright project ${project}`)
  return target
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

test('Phase 8: Admin edits a scheduled local post without losing its draft', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/news?state=all')
  const suffix = testInfo.project.name
  const originalText = `Локальная публикация ${suffix}`
  const editedText = `Исправленная локальная публикация ${suffix}`

  await page.getByRole('button', { name: 'Создать публикацию' }).click()
  const createDialog = page.getByRole('dialog', { name: 'Новая публикация в PWA' })
  await createDialog.getByLabel('Кому показать').selectOption({ index: 1 })
  await createDialog.getByLabel('Текст публикации').fill(originalText)
  await createDialog.getByLabel('Опубликовать по московскому времени').fill('2099-08-04T17:00')
  const createResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/news/local',
  )
  await createDialog.getByRole('button', { name: 'Запланировать публикацию' }).click()
  expect((await createResponse).status()).toBe(201)

  const row = page.getByText(originalText, { exact: true }).locator('xpath=ancestor::li[1]')
  await expect(row).toContainText('По расписанию')
  await row.getByRole('button', { name: /Изменить запланированную/ }).click()
  const editDialog = page.getByRole('dialog', { name: 'Изменить запланированную публикацию' })
  await editDialog.getByLabel('Текст публикации').fill(editedText)

  // Meaningful Staff input is account/entity/version scoped in localStorage.
  // A reload may close the dialog, but opening the same revision restores it.
  await page.reload()
  await page
    .getByText(originalText, { exact: true })
    .locator('xpath=ancestor::li[1]')
    .getByRole('button', { name: /Изменить запланированную/ })
    .click()
  const restoredDialog = page.getByRole('dialog', {
    name: 'Изменить запланированную публикацию',
  })
  await expect(restoredDialog.getByLabel('Текст публикации')).toHaveValue(editedText)
  await restoredDialog.getByLabel('Опубликовать по московскому времени').fill('2099-08-05T18:30')
  const updateResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      /\/staff\/api\/v1\/news\/[^/]+\/local$/.test(new URL(response.url()).pathname),
  )
  await restoredDialog.getByRole('button', { name: 'Сохранить изменения' }).click()
  expect((await updateResponse).status()).toBe(200)

  const updatedRow = page.getByText(editedText, { exact: true }).locator('xpath=ancestor::li[1]')
  await expect(updatedRow).toContainText('ревизия 2')
})

test('Phase 8: Admin corrects a published local post without moving its time', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/news?state=all')
  const originalText = `Опубликованная новость ${testInfo.project.name}`
  const correctedText = `Исправленная опубликованная новость ${testInfo.project.name}`

  await page.getByRole('button', { name: 'Создать публикацию' }).click()
  const createDialog = page.getByRole('dialog', { name: 'Новая публикация в PWA' })
  await createDialog.getByLabel('Кому показать').selectOption({ index: 1 })
  await createDialog.getByLabel('Текст публикации').fill(originalText)
  await createDialog.getByLabel('Опубликовать по московскому времени').fill('2020-08-04T17:00')
  const createResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/news/local',
  )
  await createDialog.getByRole('button', { name: 'Запланировать публикацию' }).click()
  expect((await createResponse).status()).toBe(201)

  const row = page.getByText(originalText, { exact: true }).locator('xpath=ancestor::li[1]')
  await row.getByRole('button', { name: /Исправить опубликованную/ }).click()
  const editDialog = page.getByRole('dialog', { name: 'Исправить опубликованную новость' })
  await expect(editDialog.getByLabel('Опубликовано по московскому времени')).toBeDisabled()
  await editDialog.getByLabel('Текст публикации').fill(correctedText)
  const updateResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      /\/staff\/api\/v1\/news\/[^/]+\/local$/.test(new URL(response.url()).pathname),
  )
  await editDialog.getByRole('button', { name: 'Сохранить изменения' }).click()
  const response = await updateResponse
  expect(response.status()).toBe(200)
  expect(response.request().postDataJSON()).toEqual({
    schemaVersion: 1,
    text: correctedText,
  })

  const correctedRow = page
    .getByText(correctedText, { exact: true })
    .locator('xpath=ancestor::li[1]')
  await expect(correctedRow).toContainText('ревизия 2')
  await expect(correctedRow).toContainText('обновлено')
})

test('Phase 8: Family changes real notification preferences without individual review push', async ({
  page,
}, testInfo) => {
  await loginThroughUi(
    page,
    phase8Persona(testInfo.project.name, 'family'),
    '/family/profile/notifications',
  )
  await expect(page.getByRole('heading', { name: 'Уведомления' })).toBeVisible()
  await expect(page.getByRole('switch')).toHaveCount(6)
  await expect(page.getByRole('switch', { name: 'Push: Итоги занятия' })).toBeVisible()
  await expect(page.getByText(/Отдельные push о каждой проверенной задаче/)).toBeVisible()
  await expect(page.getByRole('switch', { name: /Проверка/ })).toHaveCount(0)
  await expect(page.getByRole('switch', { name: /Аудитория/ })).toHaveCount(0)

  const news = page.getByRole('switch', { name: 'Push: Новости' })
  const initiallyEnabled = await news.isChecked()
  const firstReceipt = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname === '/family/api/v1/notifications/preferences',
  )
  await news.click()
  expect((await firstReceipt).status()).toBe(200)
  await expect(news).toBeChecked({ checked: !initiallyEnabled })

  await page.reload()
  await expect(page.getByRole('switch', { name: 'Push: Новости' })).toBeChecked({
    checked: !initiallyEnabled,
  })

  // Restore the per-browser fixture so a failed retry cannot change another run's start state.
  const restoreReceipt = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname === '/family/api/v1/notifications/preferences',
  )
  await page.getByRole('switch', { name: 'Push: Новости' }).click()
  expect((await restoreReceipt).status()).toBe(200)
  await expect(page.getByRole('switch', { name: 'Push: Новости' })).toBeChecked({
    checked: initiallyEnabled,
  })
})

test('Phase 8: Admin explicitly sends one lesson digest and Family sees it', async ({
  page,
}, testInfo) => {
  const target = digestTarget(testInfo.project.name)
  const endpoint = `/staff/api/v1/group-lessons/${target.groupLessonPublicId}/family-digest`

  // Acceptance trace: development-plan/12-phase-8-news-and-notifications.md.
  // The actual Staff page and aiohttp endpoint are used; a queue becoming empty
  // never sends this digest automatically.
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  await expect(page.getByText('Итоги для семей', { exact: true })).toBeVisible()

  const sendButton = page.getByRole('button', { name: 'Разослать итог' })
  const sentNotice = page.getByText('Итог уже разослан')
  await expect(sendButton.or(sentNotice)).toBeVisible()
  if (await sendButton.isVisible()) {
    await sendButton.click()
    await expect(page.getByRole('alertdialog')).toContainText(/Отправить итог \d+ семьям\?/)
    const sendResponse = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' && new URL(response.url()).pathname === endpoint,
    )
    await page.getByRole('button', { name: 'Отправить', exact: true }).click()
    expect((await sendResponse).status()).toBe(200)
  }
  await expect(sentNotice).toBeVisible()
  await expect(page.getByRole('button', { name: 'Разослать итог' })).toHaveCount(0)

  await loginThroughUi(
    page,
    phase8Persona(testInfo.project.name, 'family'),
    '/family/profile/notifications',
  )
  const digestEvent = page
    .getByRole('link')
    .filter({ hasText: `Начинающие · занятие ${target.lessonNumber}` })
  await expect(digestEvent.getByText('Итоги занятия готовы')).toBeVisible()

  const storedEvents = await page.evaluate(async () => {
    const response = await fetch('/family/api/v1/notification-events?unreadOnly=false')
    return (await response.json()) as {
      items: Array<{ category: string; payload: Record<string, unknown> }>
    }
  })
  expect(storedEvents.items).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        category: 'review_completed',
        payload: expect.objectContaining({
          kind: 'family_lesson_digest',
          groupLessonId: target.groupLessonPublicId,
          lessonNumber: target.lessonNumber,
        }),
      }),
    ]),
  )
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
  await page.locator(`a[href="/student/news/${postId}"]`).click()
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
  const event = page
    .locator(`a[href="/student/news/${postId}"]`)
    .filter({ hasText: 'Новая публикация' })
  await expect(event).toBeVisible()
  if (targetEvent?.readAt === null) {
    // The visibility observer may acknowledge the item between rendering the
    // badge and arming a response listener. Poll the authoritative API instead:
    // this also remains valid when a Playwright retry sees the completed write.
    // Reading requires an actually foreground document. Full-matrix Playwright
    // runs create background pages, unlike the single active browser tab a
    // student uses. A concurrent browser page can also reset scroll restoration,
    // so keep foregrounding and scrolling until the actual intersection is
    // stable enough to start the product's three-second visibility window.
    await expect
      .poll(
        async () => {
          await page.bringToFront()
          await event.scrollIntoViewIfNeeded()
          return event.evaluate((element) => {
            if (document.visibilityState !== 'visible') return 0
            const box = element.getBoundingClientRect()
            const visibleHeight = Math.max(
              0,
              Math.min(box.bottom, window.innerHeight) - Math.max(box.top, 0),
            )
            return box.height === 0 ? 0 : visibleHeight / box.height
          })
        },
        { timeout: 15_000 },
      )
      .toBeGreaterThanOrEqual(0.75)
    // Playwright's bringToFront can leave document.visibilityState at `visible`
    // without emitting a visibilitychange. Re-dispatch after proving real
    // foreground intersection so the same production timer is armed reliably.
    await page.evaluate(
      () =>
        new Promise<void>((resolve) => {
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              document.dispatchEvent(new Event('visibilitychange'))
              resolve()
            })
          })
        }),
    )
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
    return (await response.json()) as { items: Array<{ eventId: string }> }
  })
  expect(
    unreadNews.items.some(
      (item) => item.eventId === `notification.news.phase8.e2e.student.${testInfo.project.name}`,
    ),
  ).toBe(false)

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
  await page.locator(`a[href="/family/news/${postId}"]`).click()
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
