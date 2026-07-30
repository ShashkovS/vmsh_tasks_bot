import { fileURLToPath } from 'node:url'

import {
  AUTH_PERSONAS,
  credentialLabel,
  loginThroughUi,
  submitLoginForm,
  type AuthAudience,
  type AuthPersona,
} from './auth-personas'
import { expect, test, type Page } from './fixtures'

const gatewayOrigin = 'http://127.0.0.1:5380'
const problemWorkbook = fileURLToPath(
  new URL(
    '../../_external_pipelines/ВМШ 2025-26, информация для бота ВМШ — prod.xlsx',
    import.meta.url,
  ),
)

const audienceCookieNames: Record<AuthAudience, [string, string]> = {
  student: ['vmsh_student_access', 'vmsh_student_refresh'],
  family: ['vmsh_family_access', 'vmsh_family_refresh'],
  staff: ['vmsh_staff_access', 'vmsh_staff_refresh'],
}

async function browserApi(
  page: Page,
  path: string,
  init?: { method?: string; body?: string },
): Promise<{ status: number; body: unknown }> {
  return page.evaluate(
    async ({ path, init }) => {
      const response = await fetch(path, {
        method: init?.method ?? 'GET',
        credentials: 'include',
        ...(init?.body === undefined
          ? {}
          : {
              headers: { 'Content-Type': 'application/json' },
              body: init.body,
            }),
      })
      const text = await response.text()
      return { status: response.status, body: text ? (JSON.parse(text) as unknown) : null }
    },
    { path, init },
  )
}

function principal(payload: unknown): Record<string, unknown> {
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('principal' in payload) ||
    typeof payload.principal !== 'object' ||
    payload.principal === null
  ) {
    throw new Error('Authentication response has no principal')
  }
  return payload.principal as Record<string, unknown>
}

function currentSession(payload: unknown): Record<string, unknown> {
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('currentSession' in payload) ||
    typeof payload.currentSession !== 'object' ||
    payload.currentSession === null
  ) {
    throw new Error('Authentication response has no current session')
  }
  return payload.currentSession as Record<string, unknown>
}

function sessions(payload: unknown): Array<Record<string, unknown>> {
  if (
    typeof payload !== 'object' ||
    payload === null ||
    !('sessions' in payload) ||
    !Array.isArray(payload.sessions)
  ) {
    throw new Error('Authentication response has no session list')
  }
  return payload.sessions as Array<Record<string, unknown>>
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

const deepLinks: Array<{ persona: AuthPersona; target: string }> = [
  {
    persona: AUTH_PERSONAS.student,
    target: '/student/tasks/geometry-7?course=math-5-7&view=sheet#part-2',
  },
  {
    persona: AUTH_PERSONAS.family,
    target: '/family/children/masha?course=math-5-7#lesson-41',
  },
  {
    persona: AUTH_PERSONAS.teacher,
    target: '/staff/review/submission-17?queue=written#thread',
  },
]

for (const { persona, target } of deepLinks) {
  test(`${persona.audience}: anonymous deep link returns through the correct login with query and hash`, async ({
    page,
  }) => {
    await page.goto(target)
    await expect(page).toHaveURL((url) => url.pathname === `/${persona.audience}/login`)
    const loginUrl = new URL(page.url())
    expect(loginUrl.searchParams.get('returnTo')).toBe(target.slice(`/${persona.audience}`.length))

    await submitLoginForm(page, persona)
    await expect
      .poll(() => {
        const current = new URL(page.url())
        return `${current.pathname}${current.search}${current.hash}`
      })
      .toBe(target)
    await expect(page.locator(`[data-product="${persona.audience}"]`)).toBeVisible()
  })
}

const loginMatrix: Array<{
  name: string
  persona: AuthPersona
  expectedRole?: 'teacher' | 'admin'
}> = [
  { name: 'Student', persona: AUTH_PERSONAS.student },
  { name: 'Family', persona: AUTH_PERSONAS.family },
  { name: 'Teacher', persona: AUTH_PERSONAS.teacher, expectedRole: 'teacher' },
  { name: 'Admin', persona: AUTH_PERSONAS.admin, expectedRole: 'admin' },
]

for (const { name, persona, expectedRole } of loginMatrix) {
  test(`${name}: real seeded login survives reload with the authoritative principal`, async ({
    page,
    context,
  }) => {
    await loginThroughUi(page, persona)
    const beforeReload = await browserApi(page, `/${persona.audience}/api/v1/auth/me`)
    expect(beforeReload.status).toBe(200)
    expect(principal(beforeReload.body)).toMatchObject({
      accountId: persona.accountPublicId,
      audience: persona.audience,
      ...(expectedRole ? { role: expectedRole } : {}),
    })

    await page.reload()
    await expect(page.locator(`[data-product="${persona.audience}"]`)).toBeVisible()
    const afterReload = await browserApi(page, `/${persona.audience}/api/v1/auth/me`)
    expect(afterReload.status).toBe(200)
    expect(principal(afterReload.body).accountId).toBe(persona.accountPublicId)

    const cookies = await context.cookies()
    for (const cookieName of audienceCookieNames[persona.audience]) {
      expect(cookies).toContainEqual(
        expect.objectContaining({ name: cookieName, path: `/${persona.audience}` }),
      )
    }

    if (expectedRole === 'teacher') {
      await page.goto('/staff/classrooms')
      await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible()
      await expect(page.getByText('Очное воскресенье')).toHaveCount(0)
    }
    if (expectedRole === 'admin') {
      await page.goto('/staff/classrooms')
      await expect(page.getByRole('heading', { name: 'Аудитории' })).toBeVisible()
      await expect(page.getByText('Очное воскресенье')).toBeVisible()
    }
  })
}

test('Student profile uses the authenticated course enrollment instead of prototype data', async ({
  page,
}) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  await expect(page.getByRole('heading', { name: 'Алексей Тестовый-Онлайн' })).toBeVisible()
  await expect(page.getByText('Математика 5–7', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Активная группа')).toHaveValue('group-fixture-beginner')
  await expect(page.getByLabel('Формат занятий')).toHaveValue('online')
  await expect(page.getByText('Василий Петров')).toHaveCount(0)
})

test('Admin creates a course and confirms its schedule through real Staff APIs', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/courses?tab=catalog')
  await expect(page.getByRole('heading', { name: 'Курсы и группы', level: 1 })).toBeVisible()
  await expect(page.getByText('Математика 5–7', { exact: true })).toBeVisible()

  const suffix = testInfo.project.name.replace(/[^a-z0-9]/g, '')
  const name = `Физика · ${testInfo.project.name}`
  await page.getByRole('button', { name: 'Добавить курс' }).click()
  const dialog = page.getByRole('dialog', { name: 'Новый курс' })
  await dialog.getByLabel('Код').fill(`physics-${suffix}`)
  await dialog.getByLabel('Предмет').fill('physics')
  await dialog.getByLabel('Название').fill(name)
  await dialog.getByRole('button', { name: 'Сохранить' }).click()

  await expect(dialog).toBeHidden()
  await expect(page.getByText(name, { exact: true })).toBeVisible()

  await page.goto('/staff/courses?tab=schedule')
  await page.getByLabel('Курс').selectOption({ label: name })
  await page.getByRole('button', { name: 'Изменить' }).first().click()
  const scheduleDialog = page.getByRole('dialog', { name: 'Публикация условия' })
  await scheduleDialog.getByLabel('Смещение в днях').fill('0')
  await scheduleDialog.getByLabel('Время').fill('18:15')
  await scheduleDialog.getByRole('button', { name: 'Показать изменения' }).click()

  await expect(scheduleDialog).toBeHidden()
  await expect(page.getByText(/Черновик: в день цикла · 18:15/)).toBeVisible()
  await page.getByRole('button', { name: 'Подтвердить' }).first().click()
  await expect(page.getByText(/Черновик: в день цикла · 18:15/)).toHaveCount(0)
  await expect(page.getByText('в день цикла · 18:15', { exact: true })).toBeVisible()
})

test('Admin finds a student and never loses an unsaved course edit on reload', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users')
  await expect(page.getByRole('heading', { name: 'Участники и группы', level: 1 })).toBeVisible()

  await page.getByLabel('Поиск по имени').fill('алексеи')
  await expect(page.getByRole('button', { name: /Тестовый-Онлайн Алексей/ })).toBeVisible()
  await expect(page).toHaveURL((url) => url.searchParams.get('q') === 'алексеи')

  await page.getByLabel('Активная группа').selectOption('group-fixture-continuing')
  await page.getByLabel('Формат занятий').selectOption('in_person')
  await expect(page.getByText(/Несохранённые изменения хранятся/)).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('Активная группа')).toHaveValue('group-fixture-continuing')
  await expect(page.getByLabel('Формат занятий')).toHaveValue('in_person')
})

test('Teacher sees only scoped students and cannot edit admin enrollment fields', async ({
  page,
}) => {
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/users')
  await expect(page.getByRole('heading', { name: 'Участники и группы', level: 1 })).toBeVisible()
  await expect(page.getByText('Показаны только ваши группы')).toBeVisible()
  await expect(page.getByRole('button', { name: /Тестовый-Онлайн Алексей/ })).toBeVisible()
  await expect(page.getByText('Семейные аккаунты')).toHaveCount(0)
  await expect(page.getByLabel('Формат занятий')).toBeDisabled()
  await expect(page.getByLabel('Состояние записи')).toBeDisabled()
  await expect(page.getByRole('tab', { name: 'Преподаватели' })).toHaveCount(0)
})

test('Admin edits teacher scopes without losing the local draft', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite write')

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users?tab=teachers')
  await expect(page.getByRole('heading', { name: 'Преподаватели и доступы' })).toBeVisible()
  await page.getByRole('button', { name: /Преподаватель Тестовый/ }).click()

  let course = page.getByRole('group', { name: 'Доступ к курсу «Математика 5–7»' })
  const wholeCourse = course.getByRole('checkbox', { name: 'Весь курс' })
  await expect(wholeCourse).not.toBeChecked()
  await wholeCourse.click()
  await expect(page.getByText(/Несохранённые изменения хранятся/)).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: /Преподаватель Тестовый/ }).click()
  course = page.getByRole('group', { name: 'Доступ к курсу «Математика 5–7»' })
  await expect(course.getByRole('checkbox', { name: 'Весь курс' })).toBeChecked()
  const changed = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname === '/staff/api/v1/staff-members/user-staff-fixture/scopes',
  )
  await page.getByRole('button', { name: 'Сохранить доступы' }).click()
  expect((await changed).status()).toBe(200)

  // Restore the group-specific baseline for the remaining browser scenarios.
  await course.getByRole('checkbox', { name: 'Весь курс' }).click()
  await course.getByRole('checkbox', { name: 'н · Начинающие' }).click()
  const restored = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname === '/staff/api/v1/staff-members/user-staff-fixture/scopes',
  )
  await page.getByRole('button', { name: 'Сохранить доступы' }).click()
  expect((await restored).status()).toBe(200)
})

test('Admin previews the reference problem workbook', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/problems')
  await expect(page.getByRole('heading', { name: 'Настройки задач' })).toBeVisible()
  await page.getByLabel('XLSX-файл').setInputFiles(problemWorkbook)
  await page.getByRole('button', { name: 'Проверить файл' }).click()

  await expect(page.getByRole('heading', { name: 'Результат проверки' })).toBeVisible()
  await expect(
    page.getByText('Строк', { exact: true }).locator('..').getByText('1813', { exact: true }),
  ).toBeVisible()
})

test('Admin applies and rolls back the reviewed problem workbook', async ({ page }, testInfo) => {
  // All Playwright projects share one seeded SQLite database. One browser owns this reversible
  // write; preview and rendering still run in Chromium, Firefox and WebKit above.
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite write')

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/problems')
  await page.getByLabel('XLSX-файл').setInputFiles(problemWorkbook)
  await page.getByRole('button', { name: 'Проверить файл' }).click()
  await expect(page.getByRole('heading', { name: 'Результат проверки' })).toBeVisible()
  await page.getByRole('button', { name: /Применить изменения/ }).click()
  await page.getByRole('button', { name: 'Подтвердить применение' }).click()
  await expect(page.getByText('Изменения применены')).toBeVisible()
  await page.getByRole('button', { name: 'Откатить импорт' }).click()
  await page.getByRole('button', { name: 'Подтвердить откат' }).click()
  await expect(page.getByText('Импорт отменён')).toBeVisible()
})

test('Admin saves a course enrollment through the real API', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite write')

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users')
  await page.getByLabel('Поиск по имени').fill('тестов chromium')
  await expect(page.getByRole('button', { name: /Тестов chromium Ученик/ })).toBeVisible()
  await page.getByLabel('Формат занятий').selectOption('online')

  const changed = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname ===
        '/staff/api/v1/course-enrollments/enrollment-classroom-e2e-chromium',
  )
  await page.getByRole('button', { name: 'Сохранить изменения' }).click()
  expect((await changed).status()).toBe(200)
  await expect(page.getByLabel('Формат занятий')).toHaveValue('online')

  // Restore the shared baseline for later browser scenarios.
  await page.getByLabel('Формат занятий').selectOption('in_person')
  const restored = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname ===
        '/staff/api/v1/course-enrollments/enrollment-classroom-e2e-chromium',
  )
  await page.getByRole('button', { name: 'Сохранить изменения' }).click()
  expect((await restored).status()).toBe(200)
})

for (const persona of [AUTH_PERSONAS.student, AUTH_PERSONAS.family, AUTH_PERSONAS.teacher]) {
  test(`${persona.audience}: a wrong credential yields the same safe visible error`, async ({
    page,
  }) => {
    await page.goto(`/${persona.audience}/login`)
    await page.getByLabel('Логин').fill(persona.username)
    await page
      .getByLabel(credentialLabel(persona), { exact: true })
      .fill(`${persona.credential}-wrong`)
    const loginResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        new URL(response.url()).pathname === `/${persona.audience}/api/v1/auth/login`,
    )
    await page.getByRole('button', { name: 'Войти' }).click()
    const loginResponse = await loginResponsePromise

    expect(loginResponse.status()).toBe(401)
    const errorPayload = (await loginResponse.json()) as Record<string, unknown>
    expect(errorPayload).toMatchObject({ error: { code: 'invalid_credentials' } })
    expect(JSON.stringify(errorPayload)).not.toContain(persona.username)
    expect(JSON.stringify(errorPayload)).not.toContain(persona.credential)
    await expect(page.getByRole('alert')).toContainText(
      persona.audience === 'student' ? 'Логин или токен не подошли' : 'Логин или пароль не подошли',
    )
    await expect(page).toHaveURL((url) => url.pathname === `/${persona.audience}/login`)
  })
}

for (const persona of [AUTH_PERSONAS.student, AUTH_PERSONAS.family, AUTH_PERSONAS.teacher]) {
  test(`${persona.audience}: logout revokes the real session and clears audience cookies`, async ({
    page,
    context,
  }) => {
    await loginThroughUi(page, persona)
    const logout = await browserApi(page, `/${persona.audience}/api/v1/auth/logout`, {
      method: 'POST',
      body: '{}',
    })
    expect(logout.status).toBe(204)

    expect((await browserApi(page, `/${persona.audience}/api/v1/auth/me`)).status).toBe(401)
    const remainingCookies = await context.cookies()
    expect(
      remainingCookies.filter((cookie) =>
        audienceCookieNames[persona.audience].includes(cookie.name),
      ),
    ).toEqual([])

    // The authenticated boundary may already be redirecting after the 401.
    // Wait for that navigation before reloading so WebKit does not race two
    // top-level loads and report a spurious "Frame load interrupted".
    await expect(page).toHaveURL((url) => url.pathname === `/${persona.audience}/login`)
    await expect(page.getByRole('button', { name: 'Войти' })).toBeVisible()
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(page).toHaveURL((url) => url.pathname === `/${persona.audience}/login`)
    await expect(page.getByRole('button', { name: 'Войти' })).toBeVisible()
  })
}

test('one browser keeps Student, Family and Staff sessions independent', async ({
  page,
  context,
}) => {
  for (const persona of [AUTH_PERSONAS.student, AUTH_PERSONAS.family, AUTH_PERSONAS.admin]) {
    await loginThroughUi(page, persona)
  }

  for (const persona of [AUTH_PERSONAS.student, AUTH_PERSONAS.family, AUTH_PERSONAS.admin]) {
    const me = await browserApi(page, `/${persona.audience}/api/v1/auth/me`)
    expect(me.status).toBe(200)
    expect(principal(me.body).accountId).toBe(persona.accountPublicId)
  }
  const cookies = await context.cookies()
  expect(
    cookies
      .filter((cookie) => cookie.name.startsWith('vmsh_'))
      .map((cookie) => `${cookie.name}:${cookie.path}`)
      .sort(),
  ).toEqual(
    Object.entries(audienceCookieNames)
      .flatMap(([audience, names]) => names.map((name) => `${name}:/${audience}`))
      .sort(),
  )

  const familyLogout = await browserApi(page, '/family/api/v1/auth/logout', {
    method: 'POST',
    body: '{}',
  })
  expect(familyLogout.status).toBe(204)
  expect((await browserApi(page, '/family/api/v1/auth/me')).status).toBe(401)
  expect((await browserApi(page, '/student/api/v1/auth/me')).status).toBe(200)
  expect((await browserApi(page, '/staff/api/v1/auth/me')).status).toBe(200)
})

test('refresh rotates both browser cookies without changing the logical session', async ({
  page,
  context,
}) => {
  const persona = AUTH_PERSONAS.student
  await loginThroughUi(page, persona)

  const beforeContext = await browserApi(page, '/student/api/v1/auth/me')
  expect(beforeContext.status).toBe(200)
  const sessionId = currentSession(beforeContext.body).sessionId
  const cookieNames = audienceCookieNames.student
  const beforeCookies = (await context.cookies()).filter((cookie) =>
    cookieNames.includes(cookie.name),
  )
  expect(beforeCookies).toHaveLength(2)

  const refreshed = await browserApi(page, '/student/api/v1/auth/refresh', {
    method: 'POST',
    body: '{}',
  })
  expect(refreshed.status).toBe(200)
  expect(currentSession(refreshed.body).sessionId).toBe(sessionId)

  const afterCookies = (await context.cookies()).filter((cookie) =>
    cookieNames.includes(cookie.name),
  )
  expect(afterCookies).toHaveLength(2)
  for (const cookieName of cookieNames) {
    const before = beforeCookies.find((cookie) => cookie.name === cookieName)
    const after = afterCookies.find((cookie) => cookie.name === cookieName)
    expect(before, `Missing pre-refresh ${cookieName}`).toBeDefined()
    expect(after, `Missing post-refresh ${cookieName}`).toBeDefined()
    expect(after?.value).not.toBe(before?.value)
    expect(after?.path).toBe('/student')
  }

  const afterRefresh = await browserApi(page, '/student/api/v1/auth/me')
  expect(afterRefresh.status).toBe(200)
  expect(currentSession(afterRefresh.body).sessionId).toBe(sessionId)
})

test('a private reload recovers a missing access cookie through one automatic refresh', async ({
  page,
  context,
}) => {
  const persona = AUTH_PERSONAS.student
  const [accessCookieName, refreshCookieName] = audienceCookieNames.student
  await loginThroughUi(page, persona, '/student/tasks?view=list')

  const beforeCookies = await context.cookies()
  const oldAccessCookie = beforeCookies.find((cookie) => cookie.name === accessCookieName)
  expect(oldAccessCookie).toBeDefined()
  expect(beforeCookies.some((cookie) => cookie.name === refreshCookieName)).toBe(true)

  await context.clearCookies({ name: accessCookieName })
  const accessRemoved = await context.cookies()
  expect(accessRemoved.some((cookie) => cookie.name === accessCookieName)).toBe(false)
  expect(accessRemoved.some((cookie) => cookie.name === refreshCookieName)).toBe(true)

  let refreshRequestCount = 0
  page.on('request', (request) => {
    if (
      request.method() === 'POST' &&
      new URL(request.url()).pathname === '/student/api/v1/auth/refresh'
    ) {
      refreshRequestCount += 1
    }
  })

  await page.reload()
  await expect(page).toHaveURL((url) => url.pathname === '/student/tasks')
  await expect(page.locator('[data-product="student"]')).toBeVisible()
  await expect.poll(() => refreshRequestCount).toBe(1)

  const recovered = await browserApi(page, '/student/api/v1/auth/me')
  expect(recovered.status).toBe(200)
  const afterCookies = await context.cookies()
  const newAccessCookie = afterCookies.find((cookie) => cookie.name === accessCookieName)
  expect(newAccessCookie).toBeDefined()
  expect(newAccessCookie?.value).not.toBe(oldAccessCookie?.value)
  expect(afterCookies.some((cookie) => cookie.name === refreshCookieName)).toBe(true)
})

test('two tabs with one expired access cookie consume the shared refresh cookie once', async ({
  page,
  context,
}) => {
  const persona = AUTH_PERSONAS.student
  const [accessCookieName, refreshCookieName] = audienceCookieNames.student
  await loginThroughUi(page, persona, '/student/tasks?view=list')

  const secondPage = await context.newPage()
  await secondPage.emulateMedia({ reducedMotion: 'reduce' })
  await secondPage.goto('/student/news')
  await expect(secondPage.locator('[data-product="student"]')).toBeVisible()

  await context.clearCookies({ name: accessCookieName })
  const cookiesWithoutAccess = await context.cookies()
  expect(cookiesWithoutAccess.some((cookie) => cookie.name === accessCookieName)).toBe(false)
  expect(cookiesWithoutAccess.some((cookie) => cookie.name === refreshCookieName)).toBe(true)

  let refreshRequestCount = 0
  const countRefreshRequest = (request: { method(): string; url(): string }) => {
    if (
      request.method() === 'POST' &&
      new URL(request.url()).pathname === '/student/api/v1/auth/refresh'
    ) {
      refreshRequestCount += 1
    }
  }
  page.on('request', countRefreshRequest)
  secondPage.on('request', countRefreshRequest)

  await Promise.all([page.reload(), secondPage.reload()])

  await expect(page.locator('[data-product="student"]')).toBeVisible()
  await expect(secondPage.locator('[data-product="student"]')).toBeVisible()
  await expect.poll(() => refreshRequestCount).toBe(1)
  expect((await browserApi(page, '/student/api/v1/auth/me')).status).toBe(200)
  expect((await browserApi(secondPage, '/student/api/v1/auth/me')).status).toBe(200)
})

test('revoking one browser session leaves the other device active', async ({ page, context }) => {
  const persona = AUTH_PERSONAS.student
  const cookieNames = audienceCookieNames.student
  await loginThroughUi(page, persona)

  const firstContext = await browserApi(page, '/student/api/v1/auth/me')
  expect(firstContext.status).toBe(200)
  const firstSessionId = currentSession(firstContext.body).sessionId
  const firstDeviceCookies = (await context.cookies()).filter((cookie) =>
    cookieNames.includes(cookie.name),
  )
  expect(firstDeviceCookies).toHaveLength(2)

  const secondLogin = await browserApi(page, '/student/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      username: persona.username,
      telegramToken: persona.credential,
      deviceLabel: 'Second synthetic browser',
    }),
  })
  expect(secondLogin.status).toBe(200)
  const secondSessionId = currentSession(secondLogin.body).sessionId
  expect(secondSessionId).not.toBe(firstSessionId)
  const secondDeviceCookies = (await context.cookies()).filter((cookie) =>
    cookieNames.includes(cookie.name),
  )
  expect(secondDeviceCookies).toHaveLength(2)

  const listed = await browserApi(page, '/student/api/v1/auth/sessions')
  expect(listed.status).toBe(200)
  const activeSessions = sessions(listed.body)
  expect(activeSessions.map((session) => session.sessionId)).toEqual(
    expect.arrayContaining([firstSessionId, secondSessionId]),
  )
  expect(
    activeSessions.filter((session) => session.isCurrent).map((session) => session.sessionId),
  ).toEqual([secondSessionId])

  const revoked = await browserApi(
    page,
    `/student/api/v1/auth/sessions/${String(firstSessionId)}`,
    {
      method: 'DELETE',
    },
  )
  expect(revoked.status).toBe(204)
  expect((await browserApi(page, '/student/api/v1/auth/me')).status).toBe(200)

  await context.clearCookies()
  await context.addCookies(firstDeviceCookies)
  const revokedDevice = await browserApi(page, '/student/api/v1/auth/me')
  expect(revokedDevice.status).toBe(401)
  expect(revokedDevice.body).toMatchObject({ error: { code: 'authentication_required' } })

  await context.clearCookies()
  await context.addCookies(secondDeviceCookies)
  const survivingDevice = await browserApi(page, '/student/api/v1/auth/me')
  expect(survivingDevice.status).toBe(200)
  expect(currentSession(survivingDevice.body).sessionId).toBe(secondSessionId)
})

test('a Student cookie cannot authorize Family and anonymous private API is 401', async ({
  page,
}) => {
  await loginThroughUi(page, AUTH_PERSONAS.student)
  const crossAudience = await browserApi(page, '/family/api/v1/auth/sessions')
  expect(crossAudience.status).toBe(401)
  expect(crossAudience.body).toMatchObject({ error: { code: 'authentication_required' } })

  await page.context().clearCookies()
  const anonymous = await browserApi(page, '/staff/api/v1/auth/sessions')
  expect(anonymous.status).toBe(401)
  expect(anonymous.body).toMatchObject({ error: { code: 'authentication_required' } })
})

test('the one-origin gateway preserves exact auth Host/Origin and rejects spoofing', async ({
  request,
}) => {
  const exactHeaders = {
    Origin: gatewayOrigin,
    'Sec-Fetch-Site': 'same-origin',
    'X-Request-ID': 'playwright.auth.gateway',
  }
  const exactBody = {
    username: AUTH_PERSONAS.student.username,
    telegramToken: AUTH_PERSONAS.student.credential,
  }
  const exact = await request.post('/student/api/v1/auth/login', {
    headers: exactHeaders,
    data: exactBody,
  })
  expect(exact.status()).toBe(200)
  expect(exact.headers()['x-request-id']).toBe('playwright.auth.gateway')
  expect(principal(await exact.json())).toMatchObject({
    accountId: AUTH_PERSONAS.student.accountPublicId,
    audience: 'student',
  })

  const wrongOrigin = await request.post('/student/api/v1/auth/login', {
    headers: { ...exactHeaders, Origin: 'https://attacker.invalid' },
    data: exactBody,
  })
  expect(wrongOrigin.status()).toBe(403)
  expect(await wrongOrigin.json()).toMatchObject({ error: { code: 'request_source_not_allowed' } })

  const wrongHost = await request.post('/student/api/v1/auth/login', {
    headers: { ...exactHeaders, Host: 'attacker.invalid:5380' },
    data: exactBody,
  })
  expect(wrongHost.status()).toBe(403)
  expect(await wrongHost.json()).toMatchObject({ error: { code: 'request_origin_not_allowed' } })

  const spoofedForwarding = await request.post('/student/api/v1/auth/login', {
    headers: {
      ...exactHeaders,
      Forwarded: 'for=127.0.0.1;host=127.0.0.1:5380;proto=http',
    },
    data: exactBody,
  })
  expect(spoofedForwarding.status()).toBe(403)
  expect(await spoofedForwarding.json()).toMatchObject({
    error: { code: 'forwarding_headers_not_allowed' },
  })
})
