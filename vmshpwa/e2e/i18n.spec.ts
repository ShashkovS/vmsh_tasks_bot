import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

// Each journey visits several routes and can reload after an account locale change.
test.setTimeout(60_000)

// English interface: dev/development-plan/24-i18n.md, docs/i18n.md.
// The account language is saved from the personal cabinet (Staff: header menu),
// the page reloads in it, and a new device picks it up at sign-in. Fixture
// accounts are shared by all specs, so every test restores Russian.

async function saveAccountLocale(page: Page, audience: string, locale: 'ru' | 'en') {
  const status = await page.evaluate(
    async ({ audience, locale }) =>
      (
        await fetch(`/${audience}/api/v1/auth/locale`, {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ locale }),
        })
      ).status,
    { audience, locale },
  )
  expect(status).toBe(200)
}

test('Student switches the account to English in the profile', async ({ page, browser }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  try {
    await Promise.all([
      page.waitForEvent('load'),
      page.getByRole('radio', { name: 'English' }).click(),
    ])
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByRole('link', { name: 'Problems' }).first()).toBeVisible()
    await expect(page.getByText('Interface language').first()).toBeVisible()

    await page.reload()
    await expect(page.getByRole('link', { name: 'Profile' }).first()).toBeVisible()

    // A second device gets the account language right after sign-in.
    const otherDevice = await browser.newContext()
    const otherPage = await otherDevice.newPage()
    await loginThroughUi(otherPage, AUTH_PERSONAS.student, '/student/')
    await expect(otherPage.locator('html')).toHaveAttribute('lang', 'en')
    await otherDevice.close()
  } finally {
    await saveAccountLocale(page, 'student', 'ru')
  }
})

// P3 acceptance: Student home-adjacent routes, support, news and notification
// preferences use the selected interface language while server-provided names
// and message bodies remain source data.
test('Student sees English support, news, progress and notification chrome', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  try {
    await page.getByRole('radio', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    await page.goto('/student/questions')
    await expect(page.getByRole('heading', { name: 'Your questions' })).toBeVisible()

    await page.goto('/student/news')
    await expect(page.getByRole('heading', { name: 'News' })).toBeVisible()
    await expect(
      page.getByText('Posts from Telegram channels and club announcements.'),
    ).toBeVisible()

    await page.goto('/student/progress')
    await expect(page.getByRole('heading', { name: 'Progress' })).toBeVisible()

    await page.goto('/student/profile/notifications')
    await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Categories' })).toBeVisible()
  } finally {
    await saveAccountLocale(page, 'student', 'ru')
  }
})

test('Staff switches the language from the header menu', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  try {
    await page.getByRole('button', { name: 'Язык интерфейса' }).click()
    await page.getByRole('menuitem', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByRole('button', { name: 'Interface language' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Overview' }).first()).toBeVisible()
  } finally {
    await saveAccountLocale(page, 'staff', 'ru')
  }
})

// P4 acceptance: Staff review, result and statistics chrome follows the account
// locale, while course, group and person names are still server-provided data.
test('Staff sees English review, result and statistics controls', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  try {
    await page.getByRole('button', { name: 'Язык интерфейса' }).click()
    await page.getByRole('menuitem', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    await page.goto('/staff/review')
    await expect(page.getByRole('heading', { name: 'Review queue' })).toBeVisible()

    await page.goto('/staff/student-results')
    await expect(page.getByRole('heading', { name: 'Student results' })).toBeVisible()

    await page.goto('/staff/statistics?course=c-1&lesson=41')
    await expect(page.getByRole('heading', { name: 'Course statistics' })).toBeVisible()
  } finally {
    await saveAccountLocale(page, 'staff', 'ru')
  }
})

// P5 acceptance: course administration, rooms, oral windows, local news, and
// group announcements follow the account locale. Course/group names and
// authored publication text are server data and intentionally stay unchanged.
test('Staff sees English course, classroom, oral, and publishing administration', async ({
  page,
}) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  try {
    await page.getByRole('button', { name: 'Язык интерфейса' }).click()
    await page.getByRole('menuitem', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    await page.goto('/staff/courses?tab=catalog')
    await expect(page.getByRole('heading', { level: 1, name: 'Courses and groups' })).toBeVisible()

    await page.goto('/staff/courses?tab=schedule')
    await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible()

    await page.goto('/staff/classrooms?tab=catalog&roomStatus=active')
    await expect(page.getByRole('heading', { name: 'Rooms' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Room catalog' })).toBeVisible()

    await page.goto('/staff/oral?groupLesson=gl-921&tab=windows')
    await expect(page.getByRole('heading', { name: 'Oral session' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Configured windows' })).toBeVisible()

    await page.goto('/staff/news?state=all')
    await expect(page.getByRole('heading', { level: 1, name: 'News' })).toBeVisible()
    await expect(page.getByText('New PWA publication', { exact: true })).toBeVisible()

    await page.goto('/staff/broadcasts')
    await expect(page.getByRole('heading', { name: 'Mailings' })).toBeVisible()
  } finally {
    await saveAccountLocale(page, 'staff', 'ru')
  }
})

// P2 acceptance: interface chrome changes language while child and course data remain source data.
test('Family sees English child progress and notification settings', async ({ page }) => {
  await page.context().clearCookies()
  await loginThroughUi(page, AUTH_PERSONAS.family, '/family/profile')
  try {
    await page.getByRole('radio', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    await page.goto('/family/children')
    await expect(page.getByRole('heading', { name: 'Children' })).toBeVisible()
    await page
      .getByText('Алексей Тестовый-Онлайн')
      .locator('xpath=../../..')
      .getByRole('button', { name: 'Open' })
      .click()
    await expect(page.getByRole('heading', { name: 'Алексей Тестовый-Онлайн' })).toBeVisible()
    await expect(page.getByText('Course history', { exact: true })).toBeVisible()
    await expect(page.getByText(/^Lesson \d+$/, { exact: true }).first()).toBeVisible()
    await expect(page.getByText(/\d+ of \d+ problems accepted/).first()).toBeVisible()

    await page.goto('/family/profile/notifications')
    await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Recent events' })).toBeVisible()
  } finally {
    await saveAccountLocale(page, 'family', 'ru')
  }
})

test('English device language translates the sign-in page', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'vmsh-locale', value: 'en', url: baseURL ?? '' }])
  await page.goto('/family/login')
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByLabel('Password', { exact: true })).toBeVisible()
})

test('Russian stays the default without a device choice', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  await expect(page.getByText('Активная группа').first()).toBeVisible()
})

// P6: content tools change language without translating lesson/course content.
test('Staff sees English lesson, import, synonym, and whiteboard tools', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  try {
    await page.getByRole('button', { name: 'Язык интерфейса' }).click()
    await page.getByRole('menuitem', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await page.goto('/staff/lessons')
    await expect(
      page.getByRole('heading', { name: 'Lessons and publications', exact: true }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create class', exact: true })).toBeVisible()
    await page.goto('/staff/lessons/gl-921')
    await expect(page.getByText('LaTeX and publications', { exact: true })).toBeVisible()
    await page.locator('summary').filter({ hasText: 'Block before problems' }).click()
    const markdown = page.getByRole('textbox', { name: 'Block before problems: Markdown' })
    await markdown.fill('> ::video[Авторское название](https://youtu.be/dQw4w9WgXcQ)')
    await expect(page.locator('details').filter({ has: markdown }).getByRole('alert')).toHaveText(
      'Video is allowed only as a standalone top-level block',
    )
    await markdown.fill('Авторский текст **без перевода**')
    await expect(page.getByRole('region', { name: 'Draft preview', exact: true })).toContainText(
      'Авторский текст без перевода',
    )
    await page.goto('/staff/problems')
    await expect(page.getByText('XLSX file', { exact: true })).toBeVisible()
    await page.goto('/staff/problems/synonyms')
    await expect(page.getByRole('heading', { name: 'Problem synonyms', exact: true })).toBeVisible()
    await page.goto('/staff/whiteboard-export')
    await expect(
      page.getByText('Problem statements as PNG files for Zoom Whiteboard'),
    ).toBeVisible()
    await expect(page.getByText('Include statistics', { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('p6-whiteboard-en.png'), fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.getByRole('button', { name: 'Download ZIP', exact: true })).toBeVisible()
    await page.screenshot({
      path: testInfo.outputPath('p6-whiteboard-en-narrow.png'),
      fullPage: true,
    })
  } finally {
    await saveAccountLocale(page, 'staff', 'ru')
  }
})
