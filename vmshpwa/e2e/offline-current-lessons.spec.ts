import {
  studentCourseAccessResponseSchema,
  studentOfflineLessonsResponseSchema,
} from '../packages/contracts/src/courses'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

// docs/offline-current-lessons.md: real production SW + disconnected browser,
// not an API-only fetch mock. The real seed contains current lesson figures/math.
for (const mode of ['network', 'api'] as const) {
  test(`Student downloads current levels on Now and opens them after a cold offline start (${mode})`, async ({
    page,
    context,
    browserName,
  }, testInfo) => {
    test.skip(
      mode === 'network' && browserName !== 'chromium',
      'Known harness limitation: context.setOffline rejects SW navigation in Firefox/WebKit; see content-publication.spec.ts. API-disconnected coverage runs below.',
    )
    test.setTimeout(90_000)
    await loginThroughUi(page, AUTH_PERSONAS.student, '/student/')
    const current = studentOfflineLessonsResponseSchema.parse(
      await (await page.request.get('/student/api/v1/offline-lessons')).json(),
    )
    const access = studentCourseAccessResponseSchema.parse(
      await (await page.request.get('/student/api/v1/courses')).json(),
    )
    const published = current.lessons.filter(
      (lesson) => lesson.materials.condition.status === 'published',
    )
    expect(published.length).toBeGreaterThanOrEqual(2)
    await expect(page.getByText('Задачи всех уровней сохранены', { exact: true })).toBeVisible({
      timeout: 30_000,
    })
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready
      if (!navigator.serviceWorker.controller)
        await new Promise<void>((resolve) =>
          navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), {
            once: true,
          }),
        )
    })
    const assertSheet = async (target: Page, title: string) => {
      await expect(target.getByText(title, { exact: true }).first()).toBeVisible()
      await expect(target.locator('article').first()).toBeVisible()
      const figures = target.locator('article img')
      for (const figure of await figures.all()) {
        await figure.scrollIntoViewIfNeeded()
        await expect(figure).toBeVisible()
        await expect
          .poll(() =>
            figure.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0),
          )
          .toBe(true)
      }
    }
    const marker = 'offline-current-lessons-test'
    if (mode === 'network') await context.setOffline(true)
    else {
      // Same existing Phase-3 boundary proof as content-publication.spec.ts.
      // Real browser cache and real API responses were populated online; no HTTP data is mocked.
      await context.addInitScript((key) => {
        Object.defineProperty(navigator, 'onLine', {
          configurable: true,
          get: () => localStorage.getItem(key) !== '1',
        })
      }, marker)
      await page.evaluate((key) => {
        localStorage.setItem(key, '1')
        Object.defineProperty(navigator, 'onLine', {
          configurable: true,
          get: () => localStorage.getItem(key) !== '1',
        })
        dispatchEvent(new Event('offline'))
      }, marker)
      await context.route('**/student/api/**', (route) => route.abort('internetdisconnected'))
    }
    try {
      await page.getByRole('link', { name: 'Задачи', exact: true }).first().click()
      await expect(page.locator('article').first()).toBeVisible()
      await Promise.all([
        page.waitForEvent('domcontentloaded'),
        page.evaluate(() => location.reload()),
      ])
      await expect(page.locator('article').first()).toBeVisible()
      for (const lesson of published) {
        const enrollment = access.enrollments.find(
          (entry) => entry.course.courseId === lesson.courseId,
        )!
        const group = enrollment.allowedGroups.find((entry) => entry.groupId === lesson.groupId)!
        if (enrollment.course.courseId === access.enrollments[0]?.course.courseId) {
          await page
            .getByRole('group', { name: `Группа курса «${enrollment.course.name}»` })
            .getByRole('button', { name: group.name, exact: true })
            .click()
          await assertSheet(page, lesson.title || `Занятие ${lesson.lessonNumber}`)
        }
        const url = `/student/tasks/${encodeURIComponent(enrollment.course.code)}/${encodeURIComponent(group.code)}/${lesson.lessonNumber}`
        const reopened = await context.newPage()
        await reopened.goto(url)
        await assertSheet(reopened, lesson.title || `Занятие ${lesson.lessonNumber}`)
        await reopened.screenshot({
          path: testInfo.outputPath(`offline-${group.groupId}.png`),
          fullPage: true,
        })
        await reopened.close()
      }
    } finally {
      if (mode === 'network') await context.setOffline(false)
      else {
        await context.unroute('**/student/api/**')
        await page.evaluate((key) => {
          localStorage.removeItem(key)
          dispatchEvent(new Event('online'))
        }, marker)
      }
    }
    await page.reload()
    await expect(page.getByText('Задачи всех уровней сохранены', { exact: true })).toBeVisible({
      timeout: 30_000,
    })
  })
}
