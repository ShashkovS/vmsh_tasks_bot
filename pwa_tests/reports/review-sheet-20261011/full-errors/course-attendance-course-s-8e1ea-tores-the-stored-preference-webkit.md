# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: course-attendance.spec.ts >> course setting hides attendance and rooms, then restores the stored preference
- Location: e2e/course-attendance.spec.ts:7:1

# Error details

```
Error: page.goto: Frame load interrupted
Call log:
  - navigating to "http://127.0.0.1:5380/student/profile/notifications", waiting until "load"

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - banner [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - link "ВМШ 179" [ref=e7]:
            - /url: /staff/
            - generic [ref=e8]:
              - img [ref=e9]:
                - generic [ref=e12]: "179"
              - generic [ref=e13]: ВМШ 179
          - generic "Тестовый Администратор" [ref=e14]
        - generic [ref=e15]:
          - generic [ref=e16]:
            - img [ref=e17]
            - text: синхронизировано
          - button "Переключить на тёмную тему" [ref=e21]:
            - img
          - button "Язык интерфейса" [ref=e22]:
            - img
          - button "Выйти из кабинета" [ref=e23]:
            - img
    - generic [ref=e24]:
      - complementary [ref=e25]:
        - navigation "Основная навигация" [ref=e26]:
          - link "Оформление" [ref=e27]:
            - /url: /staff/branding
            - img [ref=e28]
            - generic [ref=e34]: Оформление
          - link "Сводка" [ref=e35]:
            - /url: /staff/
            - img [ref=e36]
            - generic [ref=e39]: Сводка
          - link "Проверка" [ref=e40]:
            - /url: /staff/review
            - img [ref=e41]
            - generic [ref=e45]: Проверка
          - link "Реакции" [ref=e46]:
            - /url: /staff/reactions
            - img [ref=e47]
            - generic [ref=e49]: Реакции
          - link "Вопросы" [ref=e50]:
            - /url: /staff/questions
            - img [ref=e51]
            - generic [ref=e54]: Вопросы
          - link "Тестирование" [ref=e55]:
            - /url: /staff/testing
            - img [ref=e56]
            - generic [ref=e59]: Тестирование
          - link "Очное занятие" [ref=e60]:
            - /url: /staff/in-person
            - img [ref=e61]
            - generic [ref=e65]: Очное занятие
          - link "Zoom-приём" [ref=e66]:
            - /url: /staff/oral
            - img [ref=e67]
            - generic [ref=e70]: Zoom-приём
          - link "Уроки" [ref=e71]:
            - /url: /staff/lessons
            - img [ref=e72]
            - generic [ref=e75]: Уроки
          - link "Материалы для разбора" [ref=e76]:
            - /url: /staff/whiteboard-export
            - img [ref=e77]
            - generic [ref=e80]: Материалы для разбора
          - link "Курсы" [ref=e81]:
            - /url: /staff/courses
            - img [ref=e82]
            - generic [ref=e92]: Курсы
          - link "Новости" [ref=e93]:
            - /url: /staff/news
            - img [ref=e94]
            - generic [ref=e97]: Новости
          - link "Результаты школьника" [ref=e98]:
            - /url: /staff/student-results
            - img [ref=e99]
            - generic [ref=e103]: Результаты школьника
          - link "Участники" [ref=e104]:
            - /url: /staff/users
            - img [ref=e105]
            - generic [ref=e110]: Участники
          - link "Аудитории" [ref=e111]:
            - /url: /staff/classrooms
            - img [ref=e112]
            - generic [ref=e116]: Аудитории
          - link "Рассылки" [ref=e117]:
            - /url: /staff/broadcasts
            - img [ref=e118]
            - generic [ref=e121]: Рассылки
          - link "Статистика" [ref=e122]:
            - /url: /staff/statistics
            - img [ref=e123]
            - generic [ref=e125]: Статистика
          - link "Аналитика" [ref=e126]:
            - /url: /staff/analytics
            - img [ref=e127]
            - generic [ref=e129]: Аналитика
          - link "Аудит" [ref=e130]:
            - /url: /staff/audit
            - img [ref=e131]
            - generic [ref=e134]: Аудит
      - main [ref=e135]:
        - generic [ref=e136]:
          - generic [ref=e138]:
            - generic [ref=e139]: Синтетический сезон 2025–26
            - heading "Курсы и группы" [level=1] [ref=e140]
            - generic [ref=e141]: Курс задаёт общий учебный контекст. Группы внутри него могут иметь собственные расписания и публикации.
          - generic [ref=e142]:
            - button "Добавить сезон" [ref=e144]
            - region "Курсы и группы" [ref=e145]:
              - generic [ref=e146]:
                - generic [ref=e147]:
                  - heading "Курсы и группы" [level=2] [ref=e148]
                  - paragraph [ref=e149]: Сезон 2025–2026 · названия групп уникальны только внутри курса.
                - button "Добавить курс" [ref=e150]:
                  - img
                  - text: Добавить курс
              - generic [ref=e151]:
                - generic [ref=e152]:
                  - generic [ref=e153]:
                    - generic [ref=e154]:
                      - generic [ref=e155]:
                        - paragraph [ref=e156]: physics-chromium
                        - generic [ref=e157]: Физика · chromium
                        - paragraph [ref=e158]: physics
                      - generic [ref=e159]: Черновик
                    - generic [ref=e160]:
                      - button "Настроить" [ref=e161]:
                        - img
                        - text: Настроить
                      - button "Группа" [ref=e162]:
                        - img
                        - text: Группа
                      - button "В архив" [ref=e163]:
                        - img
                        - text: В архив
                  - list [ref=e165]
                - generic [ref=e166]:
                  - generic [ref=e167]:
                    - generic [ref=e168]:
                      - generic [ref=e169]:
                        - paragraph [ref=e170]: physics-webkit
                        - generic [ref=e171]: Физика · webkit
                        - paragraph [ref=e172]: physics
                      - generic [ref=e173]: Черновик
                    - generic [ref=e174]:
                      - button "Настроить" [ref=e175]:
                        - img
                        - text: Настроить
                      - button "Группа" [ref=e176]:
                        - img
                        - text: Группа
                      - button "В архив" [ref=e177]:
                        - img
                        - text: В архив
                  - list [ref=e179]
                - generic [ref=e180]:
                  - generic [ref=e181]:
                    - generic [ref=e182]:
                      - generic [ref=e183]:
                        - paragraph [ref=e184]: math-5-7
                        - generic [ref=e185]: Математика 5–7
                        - paragraph [ref=e186]: math
                      - generic [ref=e187]: Активен
                    - generic [ref=e188]:
                      - button "Настроить" [active] [ref=e189]:
                        - img
                        - text: Настроить
                      - button "Группа" [ref=e190]:
                        - img
                        - text: Группа
                      - button "В архив" [ref=e191]:
                        - img
                        - text: В архив
                  - list [ref=e193]:
                    - listitem [ref=e194]:
                      - generic [ref=e195]:
                        - generic [ref=e196]:
                          - generic [ref=e197]: н
                          - text: Начинающие
                        - paragraph [ref=e198]: 7 учеников · расписание группы
                      - generic [ref=e199]:
                        - generic [ref=e200]: Активна
                        - button "Изменить группу Начинающие" [ref=e201]:
                          - img
                    - listitem [ref=e202]:
                      - generic [ref=e203]:
                        - generic [ref=e204]:
                          - generic [ref=e205]: п
                          - text: Продолжающие
                        - paragraph [ref=e206]: 3 учеников · расписание группы
                      - generic [ref=e207]:
                        - generic [ref=e208]: Активна
                        - button "Изменить группу Продолжающие" [ref=e209]:
                          - img
                    - listitem [ref=e210]:
                      - generic [ref=e211]:
                        - generic [ref=e212]:
                          - generic [ref=e213]: э
                          - text: Эксперты
                        - paragraph [ref=e214]: 0 учеников · расписание группы
                      - generic [ref=e215]:
                        - generic [ref=e216]: Активна
                        - button "Изменить группу Эксперты" [ref=e217]:
                          - img
                    - listitem [ref=e218]:
                      - generic [ref=e219]:
                        - generic [ref=e220]:
                          - generic [ref=e221]: т
                          - text: Тестирование
                        - paragraph [ref=e222]: 0 учеников · расписание группы
                      - generic [ref=e223]:
                        - generic [ref=e224]: Активна
                        - button "Изменить группу Тестирование" [ref=e225]:
                          - img
                    - listitem [ref=e226]:
                      - generic [ref=e227]:
                        - generic [ref=e228]:
                          - generic [ref=e229]: "@"
                          - text: Без группы
                        - paragraph [ref=e230]: 0 учеников · расписание группы
                      - generic [ref=e231]:
                        - generic [ref=e232]: Скрыта
                        - button "Изменить группу Без группы" [ref=e233]:
                          - img
                    - listitem [ref=e234]:
                      - generic [ref=e235]:
                        - generic [ref=e236]:
                          - generic [ref=e237]: ec
                          - text: Начинающие E2E chromium
                        - paragraph [ref=e238]: 1 учеников · расписание группы
                      - generic [ref=e239]:
                        - generic [ref=e240]: Активна
                        - button "Изменить группу Начинающие E2E chromium" [ref=e241]:
                          - img
                    - listitem [ref=e242]:
                      - generic [ref=e243]:
                        - generic [ref=e244]:
                          - generic [ref=e245]: ew
                          - text: Начинающие E2E webkit
                        - paragraph [ref=e246]: 2 учеников · расписание группы
                      - generic [ref=e247]:
                        - generic [ref=e248]: Активна
                        - button "Изменить группу Начинающие E2E webkit" [ref=e249]:
                          - img
                    - listitem [ref=e250]:
                      - generic [ref=e251]:
                        - generic [ref=e252]:
                          - generic [ref=e253]: ef
                          - text: Начинающие E2E firefox
                        - paragraph [ref=e254]: 2 учеников · расписание группы
                      - generic [ref=e255]:
                        - generic [ref=e256]: Активна
                        - button "Изменить группу Начинающие E2E firefox" [ref=e257]:
                          - img
                - generic [ref=e258]:
                  - generic [ref=e259]:
                    - generic [ref=e260]:
                      - generic [ref=e261]:
                        - paragraph [ref=e262]: archive-results
                        - generic [ref=e263]: Архивный курс
                        - paragraph [ref=e264]: math
                      - generic [ref=e265]: В архиве
                    - generic [ref=e266]:
                      - button "Настроить" [ref=e267]:
                        - img
                        - text: Настроить
                      - button "Группа" [ref=e268]:
                        - img
                        - text: Группа
                      - button "Восстановить" [ref=e269]:
                        - img
                        - text: Восстановить
                  - list [ref=e271]:
                    - listitem [ref=e272]:
                      - generic [ref=e273]:
                        - generic [ref=e274]:
                          - generic [ref=e275]: arch
                          - text: Архивный уровень
                        - paragraph [ref=e276]: 0 учеников · расписание группы
                      - generic [ref=e277]:
                        - generic [ref=e278]: Скрыта
                        - button "Изменить группу Архивный уровень" [ref=e279]:
                          - img
            - generic [ref=e280]:
              - generic [ref=e281]:
                - generic [ref=e283]: "Физика · chromium: вердикты письменных задач"
                - generic [ref=e284]:
                  - generic [ref=e285]:
                    - text: Набор вердиктов
                    - combobox "Набор вердиктов" [ref=e286]:
                      - option "+ и −"
                      - option "+, +/2 и −" [selected]
                      - 'option "Полная шкала: +, +., ±, +/2, ∓, −., −"'
                  - button "Сохранить шкалу" [disabled]
                  - paragraph [ref=e287]: Нулевой результат означает, что школьник ничего не сдавал, и преподавателем не выбирается.
              - generic [ref=e288]:
                - generic [ref=e290]: "Физика · webkit: вердикты письменных задач"
                - generic [ref=e291]:
                  - generic [ref=e292]:
                    - text: Набор вердиктов
                    - combobox "Набор вердиктов" [ref=e293]:
                      - option "+ и −"
                      - option "+, +/2 и −" [selected]
                      - 'option "Полная шкала: +, +., ±, +/2, ∓, −., −"'
                  - button "Сохранить шкалу" [disabled]
                  - paragraph [ref=e294]: Нулевой результат означает, что школьник ничего не сдавал, и преподавателем не выбирается.
              - generic [ref=e295]:
                - generic [ref=e297]: "Математика 5–7: вердикты письменных задач"
                - generic [ref=e298]:
                  - generic [ref=e299]:
                    - text: Набор вердиктов
                    - combobox "Набор вердиктов" [ref=e300]:
                      - option "+ и −"
                      - option "+, +/2 и −"
                      - 'option "Полная шкала: +, +., ±, +/2, ∓, −., −" [selected]'
                  - button "Сохранить шкалу" [disabled]
                  - paragraph [ref=e301]: Нулевой результат означает, что школьник ничего не сдавал, и преподавателем не выбирается.
  - generic:
    - region "Notifications"
```

# Test source

```ts
  1   | import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
  2   | import { expect, test } from './fixtures'
  3   | import { publishedClassroomAssignmentListResponseSchema } from '../packages/contracts/src/classrooms'
  4   | import { adminCourseCatalogResponseSchema } from '../packages/contracts/src/admin-course-catalog'
  5   |
  6   | // docs/course-attendance-settings.md: real versioned admin toggle and both audiences.
  7   | test('course setting hides attendance and rooms, then restores the stored preference', async ({
  8   |   page,
  9   |   browser,
  10  | }, info) => {
  11  |   test.setTimeout(90_000)
  12  |   await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/courses?tab=catalog')
  13  |   const original = adminCourseCatalogResponseSchema
  14  |     .parse(await (await page.request.get('/staff/api/v1/courses')).json())
  15  |     .courses.find((course) => course.courseId === 'c-1')!
  16  |   const update = async (enabled: boolean) => {
  17  |     const course = adminCourseCatalogResponseSchema
  18  |       .parse(await (await page.request.get('/staff/api/v1/courses')).json())
  19  |       .courses.find((item) => item.courseId === 'c-1')!
  20  |     const response = await page.request.put('/staff/api/v1/courses/c-1', {
  21  |       headers: { Origin: 'http://127.0.0.1:5380', 'If-Match': `"c-1:v${course.version}"` },
  22  |       data: {
  23  |         schemaVersion: 1,
  24  |         code: course.code,
  25  |         name: course.name,
  26  |         subjectCode: course.subjectCode,
  27  |         status: course.status,
  28  |         sortOrder: course.sortOrder,
  29  |         accentKey: course.accentKey,
  30  |         hasInPersonClasses: enabled,
  31  |       },
  32  |     })
  33  |     expect(response.ok()).toBe(true)
  34  |   }
  35  |   try {
  36  |     // Other release scenarios create courses; select the fixture's course by
  37  |     // its stable code rather than whichever card sorts first.
  38  |     const courseCard = page
  39  |       .locator('[data-slot="card"]')
  40  |       .filter({ has: page.getByText(original.code, { exact: true }) })
  41  |     await courseCard.getByRole('button', { name: 'Настроить', exact: true }).click()
  42  |     await expect(page.getByRole('checkbox', { name: 'В курсе есть очные занятия' })).toBeChecked()
  43  |     await page.getByRole('checkbox', { name: 'В курсе есть очные занятия' }).uncheck()
  44  |     const saved = page.waitForResponse(
  45  |       (response) =>
  46  |         response.request().method() === 'PUT' &&
  47  |         new URL(response.url()).pathname === '/staff/api/v1/courses/c-1',
  48  |     )
  49  |     await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  50  |     expect((await saved).ok()).toBe(true)
  51  |     for (const audience of ['student', 'family'] as const) {
  52  |       const context = await browser.newContext({
  53  |         baseURL: 'http://127.0.0.1:5380',
  54  |         viewport: { width: 390, height: 844 },
  55  |       })
  56  |       try {
  57  |         const visitor = await context.newPage()
  58  |         await loginThroughUi(
  59  |           visitor,
  60  |           audience === 'student' ? AUTH_PERSONAS.studentInPerson : AUTH_PERSONAS.family,
  61  |           audience === 'student' ? '/student/profile' : '/family/children/u-102',
  62  |         )
  63  |         await expect(visitor.getByText('Математика 5–7', { exact: true }).first()).toBeVisible()
  64  |         await expect(visitor.getByLabel('Формат занятий')).toHaveCount(0)
  65  |         await expect(visitor.getByText('Очно', { exact: true })).toHaveCount(0)
  66  |         await expect(visitor.getByText('Онлайн', { exact: true })).toHaveCount(0)
  67  |         await visitor.screenshot({
  68  |           path: info.outputPath(`${audience}-attendance-disabled.png`),
  69  |           fullPage: true,
  70  |         })
  71  |         await visitor.goto(`/${audience}/`)
  72  |         await expect(
  73  |           visitor.getByRole('heading', { name: 'Очные занятия', exact: true }),
  74  |         ).toHaveCount(0)
  75  |         const rooms = await visitor.request.get(
  76  |           audience === 'student'
  77  |             ? '/student/api/v1/classroom-assignments'
  78  |             : '/family/api/v1/children/u-102/classroom-assignments',
  79  |         )
  80  |         expect(
  81  |           publishedClassroomAssignmentListResponseSchema.parse(await rooms.json())
  82  |             .hasInPersonCourses,
  83  |         ).toBe(false)
> 84  |         await visitor.goto(`/${audience}/profile/notifications`)
      |                       ^ Error: page.goto: Frame load interrupted
  85  |         await expect(visitor.getByText('Очное занятие', { exact: true })).toHaveCount(0)
  86  |       } finally {
  87  |         await context.close()
  88  |       }
  89  |     }
  90  |     await update(true)
  91  |     const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5380' })
  92  |     try {
  93  |       const student = await context.newPage()
  94  |       await loginThroughUi(student, AUTH_PERSONAS.studentInPerson, '/student/profile')
  95  |       await expect(student.getByLabel('Формат занятий')).toHaveValue('in_person')
  96  |     } finally {
  97  |       await context.close()
  98  |     }
  99  |   } finally {
  100 |     await update(original.hasInPersonClasses)
  101 |   }
  102 | })
  103 |
```
