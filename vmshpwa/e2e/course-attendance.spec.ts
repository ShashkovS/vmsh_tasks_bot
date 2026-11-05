import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'
import { publishedClassroomAssignmentListResponseSchema } from '../packages/contracts/src/classrooms'
import { adminCourseCatalogResponseSchema } from '../packages/contracts/src/admin-course-catalog'

// docs/course-attendance-settings.md: real versioned admin toggle and both audiences.
test('course setting hides attendance and rooms, then restores the stored preference', async ({
  page,
  browser,
}, info) => {
  test.setTimeout(90_000)
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/courses?tab=catalog')
  const original = adminCourseCatalogResponseSchema
    .parse(await (await page.request.get('/staff/api/v1/courses')).json())
    .courses.find((course) => course.courseId === 'c-1')!
  const update = async (enabled: boolean) => {
    const course = adminCourseCatalogResponseSchema
      .parse(await (await page.request.get('/staff/api/v1/courses')).json())
      .courses.find((item) => item.courseId === 'c-1')!
    const response = await page.request.put('/staff/api/v1/courses/c-1', {
      headers: { Origin: 'http://127.0.0.1:5380', 'If-Match': `"c-1:v${course.version}"` },
      data: {
        schemaVersion: 1,
        code: course.code,
        name: course.name,
        subjectCode: course.subjectCode,
        status: course.status,
        sortOrder: course.sortOrder,
        accentKey: course.accentKey,
        hasInPersonClasses: enabled,
      },
    })
    expect(response.ok()).toBe(true)
  }
  try {
    // Other release scenarios create courses; select the fixture's course by
    // its stable code rather than whichever card sorts first.
    const courseCard = page
      .locator('[data-slot="card"]')
      .filter({ has: page.getByText(original.code, { exact: true }) })
    await courseCard.getByRole('button', { name: 'Настроить', exact: true }).click()
    await expect(page.getByRole('checkbox', { name: 'В курсе есть очные занятия' })).toBeChecked()
    await page.getByRole('checkbox', { name: 'В курсе есть очные занятия' }).uncheck()
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' &&
        new URL(response.url()).pathname === '/staff/api/v1/courses/c-1',
    )
    await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
    expect((await saved).ok()).toBe(true)
    for (const audience of ['student', 'family'] as const) {
      const context = await browser.newContext({
        baseURL: 'http://127.0.0.1:5380',
        viewport: { width: 390, height: 844 },
      })
      try {
        const visitor = await context.newPage()
        await loginThroughUi(
          visitor,
          audience === 'student' ? AUTH_PERSONAS.studentInPerson : AUTH_PERSONAS.family,
          audience === 'student' ? '/student/profile' : '/family/children/u-102',
        )
        await expect(visitor.getByText('Математика 5–7', { exact: true }).first()).toBeVisible()
        await expect(visitor.getByLabel('Формат занятий')).toHaveCount(0)
        await expect(visitor.getByText('Очно', { exact: true })).toHaveCount(0)
        await expect(visitor.getByText('Онлайн', { exact: true })).toHaveCount(0)
        await visitor.screenshot({
          path: info.outputPath(`${audience}-attendance-disabled.png`),
          fullPage: true,
        })
        await visitor.goto(`/${audience}/`)
        await expect(
          visitor.getByRole('heading', { name: 'Очные занятия', exact: true }),
        ).toHaveCount(0)
        const rooms = await visitor.request.get(
          audience === 'student'
            ? '/student/api/v1/classroom-assignments'
            : '/family/api/v1/children/u-102/classroom-assignments',
        )
        expect(
          publishedClassroomAssignmentListResponseSchema.parse(await rooms.json())
            .hasInPersonCourses,
        ).toBe(false)
        await visitor.goto(`/${audience}/profile/notifications`)
        await expect(visitor.getByText('Очное занятие', { exact: true })).toHaveCount(0)
      } finally {
        await context.close()
      }
    }
    await update(true)
    const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5380' })
    try {
      const student = await context.newPage()
      await loginThroughUi(student, AUTH_PERSONAS.studentInPerson, '/student/profile')
      await expect(student.getByLabel('Формат занятий')).toHaveValue('in_person')
    } finally {
      await context.close()
    }
  } finally {
    await update(original.hasInPersonClasses)
  }
})
