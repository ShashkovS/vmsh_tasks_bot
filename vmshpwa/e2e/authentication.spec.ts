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
      await page.goto('/staff/audit')
      await expect(page.getByRole('heading', { name: 'Нет доступа' })).toBeVisible()
    }
    if (expectedRole === 'admin') {
      await page.goto('/staff/classrooms')
      await expect(page.getByRole('heading', { name: 'Аудитории' })).toBeVisible()
      await expect(page.getByText('Очное воскресенье')).toBeVisible()
    }
  })
}

test('Admin searches the real immutable audit timeline', async ({ page }) => {
  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    '/staff/audit?objectType=all&q=e2e.audit.baseline',
  )
  await expect(page.getByRole('heading', { name: 'Журнал изменений', level: 1 })).toBeVisible()
  await expect(page.getByText('e2e.audit.baseline', { exact: true })).toBeVisible()
  await expect(page.getByText('account-student-fixture', { exact: true })).toBeVisible()

  await page.getByText('Показать изменения').click()
  await expect(page.getByText('blocked', { exact: true })).toBeVisible()
  await expect(page.getByText('active', { exact: true })).toBeVisible()
  await expect(page).toHaveURL((url) => url.searchParams.get('q') === 'e2e.audit.baseline')
})

test('Teacher reads only the scoped anonymous course statistics', async ({ page }) => {
  await loginThroughUi(
    page,
    AUTH_PERSONAS.teacher,
    '/staff/statistics?course=course-fixture-math-5-7&lesson=41',
  )
  await expect(page.getByRole('heading', { name: 'Статистика курса', level: 1 })).toBeVisible()
  await expect(page.getByLabel('Группа')).toHaveValue('')
  await expect(page.getByRole('button', { name: 'Занятие 41' })).toHaveAttribute(
    'aria-current',
    'true',
  )
  await expect(page.getByRole('img', { name: /Распределение по группе/ })).toBeVisible()
  const aggregateCard = page.locator('[data-slot="card"]').filter({ hasText: 'Состав агрегата' })
  await expect(aggregateCard.getByText('Начинающие', { exact: true })).toBeVisible()
  await expect(page.getByText('Продолжающие', { exact: true })).toHaveCount(0)
  await expect(page.getByText(/маркера или позиции отдельного школьника/)).toBeVisible()
  await expect(page).toHaveURL((url) => url.searchParams.get('lesson') === '41')
})

test('Teacher home loads the real scoped operational dashboard', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/')
  await expect(page.getByRole('heading', { name: 'Рабочая сводка', level: 1 })).toBeVisible()
  await expect(page.getByText('Ожидают проверки', { exact: true })).toBeVisible()
  await expect(page.getByText('Занятия по группам', { exact: true })).toBeVisible()

  const response = await browserApi(page, '/staff/api/v1/dashboard')
  expect(response.status).toBe(200)
  expect(response.body).toMatchObject({
    schemaVersion: 1,
    summary: {
      review: { totalCases: expect.any(Number), claimedByOthers: expect.any(Number) },
      questions: { awaitingStaff: expect.any(Number), olderThanOneHour: expect.any(Number) },
      delivery: null,
    },
    lessons: expect.any(Array),
  })
  expect(JSON.stringify(response.body)).not.toContain('studentId')
})

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

test('Admin creates a Family login without persisting its password in the browser', async ({
  page,
}, testInfo) => {
  // Browser projects share one isolated SQLite database. One unique account is
  // enough to prove the Staff write and the subsequent real Family login.
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite write')

  const suffix = Date.now().toString(36)
  const username = `family-created-${suffix}`
  const password = AUTH_PERSONAS.family.credential
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users')
  await page.getByLabel('Поиск по имени').fill('тестов chromium')
  await expect(page.getByRole('button', { name: /Тестов chromium Ученик/ })).toBeVisible()

  await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click()
  await page.getByLabel('Логин').fill(username)
  await page.getByLabel('Имя аккаунта').fill('Семья browser E2E')
  await page.getByLabel('Первый пароль').fill(password)
  await expect(page.getByText(/Пароль — никогда/)).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click()
  await expect(page.getByLabel('Логин')).toHaveValue(username)
  await expect(page.getByLabel('Имя аккаунта')).toHaveValue('Семья browser E2E')
  await expect(page.getByLabel('Первый пароль')).toHaveValue('')
  await page.getByLabel('Первый пароль').fill(password)

  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/family-accounts'),
  )
  await page.getByRole('button', { name: 'Создать и привязать' }).click()
  const response = await created
  expect(response.status()).toBe(201)
  const responseText = await response.text()
  expect(responseText).not.toContain(password)
  expect(responseText).not.toContain('password')
  await expect(page.getByText(`${username} · родитель · основной контакт`)).toBeVisible()

  await page.context().clearCookies()
  const familyPersona: AuthPersona = {
    persona: 'family',
    accountPublicId: 'created-by-family-account-e2e',
    audience: 'family',
    username,
    credentialField: 'password',
    credential: password,
  }
  await loginThroughUi(page, familyPersona, '/family/children')
  await expect(page.getByText('Ученик Тестов chromium')).toBeVisible()
})

test('Admin creates a Student web login backed by the current bot token', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite write')

  const project = testInfo.project.name
  const username = `student-created-${Date.now().toString(36)}`
  const telegramToken = `synthetic-provision-${project}-not-a-secret`
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users')
  await page.getByLabel('Поиск по имени').fill(`безаккаунта ${project}`)
  await expect(page.getByRole('button', { name: /БезАккаунта chromium Новый/ })).toBeVisible()

  await page.getByLabel('Логин школьника').fill(username)
  await expect(page.getByText(/Несохранённый логин хранится/)).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Логин школьника')).toHaveValue(username)

  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/student-account'),
  )
  await page.getByRole('button', { name: 'Создать web-вход' }).click()
  const response = await created
  expect(response.status()).toBe(201)
  expect(await response.text()).not.toContain(telegramToken)
  await expect(page.getByText('Web-вход активен')).toBeVisible()
  await expect(page.getByText(username, { exact: true })).toBeVisible()

  await page.context().clearCookies()
  await loginThroughUi(
    page,
    {
      persona: 'student',
      accountPublicId: 'created-student-account-e2e',
      audience: 'student',
      username,
      credentialField: 'telegramToken',
      credential: telegramToken,
    },
    '/student/profile',
  )
  await expect(page.getByRole('heading', { name: `Новый БезАккаунта ${project}` })).toBeVisible()
})

test('Admin creates a small Student account batch and keeps selection across reload', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite batch')

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users')
  await page.getByRole('button', { name: 'Выбрать школьников' }).click()
  await page.getByLabel('Поиск среди готовых').fill('пакет chromium')
  await page.getByRole('button', { name: 'Выбрать найденных · 2' }).click()
  await expect(page.getByText(/Выбрано: 2\. Выбор хранится/)).toBeVisible()

  await page.reload()
  await expect(page.getByRole('button', { name: 'Создать аккаунты · 2' })).toBeEnabled()

  let accountResponses = 0
  const secondCreated = page.waitForResponse((response) => {
    if (
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/student-account')
    ) {
      accountResponses += 1
    }
    return accountResponses === 2
  })
  await page.getByRole('button', { name: 'Создать аккаунты · 2' }).click()
  expect((await secondCreated).status()).toBe(201)
  await expect(page.getByText('Создано: 2. Ошибок: 0.')).toBeVisible()
})

test('Deploy-first: Admin imports a Student TSV, enrolls the account and Student logs in', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite writes')

  const suffix = Date.now().toString(36)
  const username = `pilot-student-${suffix}`
  const telegramToken = `pilot-telegram-token-${suffix}`

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users?tab=imports')
  const studentSource = page.getByLabel('Вставьте строки из таблицы').first()
  await studentSource.fill(`Приёмочный\tШкольник\t\t2012-03-04\t7\t${username}\t${telegramToken}`)
  const studentPreview = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/imports/student-accounts/preview'),
  )
  await page.getByRole('button', { name: 'Проверить таблицу' }).first().click()
  expect((await studentPreview).status()).toBe(200)
  await expect(page.getByText(username, { exact: true })).toBeVisible()

  const studentApply = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/imports/student-accounts/apply'),
  )
  await page.getByRole('button', { name: 'Создать готовые · 1' }).click()
  expect((await studentApply).status()).toBe(201)
  await expect(page.getByText('Создано: 1. Пропущено: 0.')).toBeVisible()

  await page.getByLabel('Вставьте строки зачисления').fill(`${username}\tmath-5-7\tн,п`)
  const enrollmentPreview = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/imports/course-enrollments/preview'),
  )
  await page.getByRole('button', { name: 'Проверить зачисление' }).click()
  expect((await enrollmentPreview).status()).toBe(200)
  await expect(page.getByText(`${username} · math-5-7`, { exact: true })).toBeVisible()

  const enrollmentApply = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/imports/course-enrollments/apply'),
  )
  await page.getByRole('button', { name: 'Зачислить готовых · 1' }).click()
  expect((await enrollmentApply).status()).toBe(201)
  await expect(page.getByText('Зачислено: 1. Пропущено: 0.')).toBeVisible()

  await page.context().clearCookies()
  await loginThroughUi(
    page,
    {
      persona: 'student',
      accountPublicId: 'deploy-first-imported-student',
      audience: 'student',
      username,
      credentialField: 'telegramToken',
      credential: telegramToken,
    },
    '/student/profile',
  )
  await expect(page.getByRole('heading', { name: 'Школьник Приёмочный' })).toBeVisible()
  await expect(page.getByLabel('Активная группа')).toHaveValue('group-fixture-beginner')
})

test('Deploy-first: Admin creates a Teacher, grants a course and Teacher logs in', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite writes')

  const suffix = Date.now().toString(36)
  const username = `pilot-teacher-${suffix}`
  const password = `pilot-password-${suffix}`

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users?tab=teachers')
  await page.getByRole('button', { name: 'Добавить преподавателя' }).click()
  const creator = page.locator('form').filter({ hasText: 'Временный пароль' })
  await creator.getByLabel('Фамилия').fill('Приёмочный')
  await creator.getByLabel('Имя').fill('Преподаватель')
  await creator.getByLabel('Логин').fill(username)
  await creator.getByLabel('Временный пароль').fill(password)
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/staff-members',
  )
  await creator.getByRole('button', { name: 'Создать преподавателя' }).click()
  expect((await created).status()).toBe(201)

  await page.getByRole('button', { name: /Приёмочный Преподаватель/ }).click()
  const course = page.getByRole('group', { name: 'Доступ к курсу «Математика 5–7»' })
  await course.getByRole('checkbox', { name: 'Весь курс' }).click()
  const scopesSaved = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      /\/staff-members\/[^/]+\/scopes$/.test(new URL(response.url()).pathname),
  )
  await page.getByRole('button', { name: 'Сохранить доступы' }).click()
  expect((await scopesSaved).status()).toBe(200)

  await page.context().clearCookies()
  await loginThroughUi(
    page,
    {
      persona: 'teacher',
      accountPublicId: 'deploy-first-created-teacher',
      audience: 'staff',
      username,
      credentialField: 'password',
      credential: password,
    },
    '/staff/',
  )
  await expect(page.getByRole('heading', { name: 'Рабочая сводка', level: 1 })).toBeVisible()
  expect((await browserApi(page, '/staff/api/v1/dashboard')).status).toBe(200)
})

test('Deploy-first: Admin imports a Teacher batch with shared course access', async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'One browser proves the shared SQLite writes')

  const suffix = Date.now().toString(36)
  const firstUsername = `pilot-batch-one-${suffix}`
  const secondUsername = `pilot-batch-two-${suffix}`
  const password = `pilot-batch-password-${suffix}`

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users?tab=teachers')
  await page.getByRole('button', { name: 'Пакетная загрузка' }).click()
  await page
    .getByLabel('Вставьте преподавателей из таблицы')
    .fill(
      `Пакетный\tПервый\t\t${firstUsername}\t${password}\n` +
        `Пакетный\tВторой\tТестович\t${secondUsername}\t${password}`,
    )
  await page.getByRole('checkbox', { name: 'Математика 5–7 · весь курс' }).click()

  await page.reload()
  await page.getByRole('button', { name: 'Пакетная загрузка' }).click()
  await expect(page.getByLabel('Вставьте преподавателей из таблицы')).toHaveValue(
    new RegExp(firstUsername),
  )
  await expect(page.getByRole('checkbox', { name: 'Математика 5–7 · весь курс' })).toBeChecked()

  await page.getByRole('button', { name: 'Проверить таблицу' }).click()
  await expect(page.getByText(firstUsername, { exact: true })).toBeVisible()
  await expect(page.getByText(secondUsername, { exact: true })).toBeVisible()

  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/staff-members/batch',
  )
  await page.getByRole('button', { name: 'Создать преподавателей · 2' }).click()
  expect((await created).status()).toBe(201)
  await expect(page.getByText('Создано: 2.')).toBeVisible()

  await page.context().clearCookies()
  await loginThroughUi(
    page,
    {
      persona: 'teacher',
      accountPublicId: 'deploy-first-batch-teacher',
      audience: 'staff',
      username: firstUsername,
      credentialField: 'password',
      credential: password,
    },
    '/staff/',
  )
  await expect(page.getByRole('heading', { name: 'Рабочая сводка', level: 1 })).toBeVisible()
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
  const attendanceMode = page.getByLabel('Формат занятий')
  const originalMode = await attendanceMode.inputValue()
  const changedMode = originalMode === 'online' ? 'in_person' : 'online'
  await attendanceMode.selectOption(changedMode)

  const changed = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname ===
        '/staff/api/v1/course-enrollments/enrollment-classroom-e2e-chromium',
  )
  await page.getByRole('button', { name: 'Сохранить изменения' }).click()
  expect((await changed).status()).toBe(200)
  await expect(attendanceMode).toHaveValue(changedMode)

  // Restore the exact state observed by this attempt. This keeps Playwright
  // retries valid even when the previous attempt reached the first write.
  await attendanceMode.selectOption(originalMode)
  const restored = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname ===
        '/staff/api/v1/course-enrollments/enrollment-classroom-e2e-chromium',
  )
  await page.getByRole('button', { name: 'Сохранить изменения' }).click()
  expect((await restored).status()).toBe(200)
  await expect(attendanceMode).toHaveValue(originalMode)
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
    // Firefox can expose the just-expired deletion cookie for one event-loop
    // turn even though the following authenticated request is already rejected.
    await expect
      .poll(async () => {
        const remainingCookies = await context.cookies()
        return remainingCookies.filter((cookie) =>
          audienceCookieNames[persona.audience].includes(cookie.name),
        ).length
      })
      .toBe(0)

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
  const refreshCookie = beforeCookies.find((cookie) => cookie.name === refreshCookieName)
  expect(oldAccessCookie).toBeDefined()
  expect(refreshCookie).toBeDefined()
  if (!refreshCookie) throw new Error(`Missing pre-refresh ${refreshCookieName}`)

  await context.clearCookies({ name: accessCookieName })
  // Playwright implements a filtered clear differently across engines. Put
  // the intentionally retained HttpOnly cookie back explicitly before the
  // reload so the test never observes an intermediate empty browser jar.
  await context.addCookies([refreshCookie])
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
