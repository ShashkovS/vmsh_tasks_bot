# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: problem-release.spec.ts >> teacher releases fifteen tasks progressively to Student and Family
- Location: e2e/problem-release.spec.ts:5:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByRole('heading', { name: /^Задача / })
Expected: 15
Received: 5
Timeout:  30000ms

Call log:
  - Expect "toHaveCount" with timeout 30000ms
  - waiting for getByRole('heading', { name: /^Задача / })
    63 × locator resolved to 5 elements
       - unexpected value "5"

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - banner [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - link "ВМШ 179" [ref=e7] [cursor=pointer]:
            - /url: /student/
            - generic [ref=e8]:
              - img [ref=e9]: "179"
              - generic [ref=e13]: ВМШ 179
          - generic "Алексей Тестовый-Онлайн" [ref=e14]
        - button "Переключить на тёмную тему" [active] [ref=e16]:
          - img
    - generic [ref=e17]:
      - complementary [ref=e18]:
        - navigation "Основная навигация" [ref=e19]:
          - link "Сейчас" [ref=e20] [cursor=pointer]:
            - /url: /student/
            - img [ref=e21]
            - generic [ref=e24]: Сейчас
          - link "Задачи" [ref=e25] [cursor=pointer]:
            - /url: /student/tasks
            - img [ref=e26]
            - generic [ref=e33]: Задачи
          - link "Новости" [ref=e34] [cursor=pointer]:
            - /url: /student/news
            - img [ref=e35]
            - generic [ref=e40]: Новости
          - link "Прогресс" [ref=e41] [cursor=pointer]:
            - /url: /student/progress
            - img [ref=e42]
            - generic [ref=e45]: Прогресс
          - link "Профиль" [ref=e46] [cursor=pointer]:
            - /url: /student/profile
            - img [ref=e47]
            - generic [ref=e50]: Профиль
      - main [ref=e51]:
        - status [ref=e52]:
          - img [ref=e53]
          - generic [ref=e58]:
            - generic [ref=e59]: Восстанавливаем связь…
            - paragraph [ref=e60]: Показана последняя сохранённая копия от 11 окт. 2026 г., 20:46. Новые публикации и изменения появятся после восстановления связи.
        - status [ref=e61]: Задачи всех уровней сохранены
        - generic [ref=e65]:
          - generic [ref=e66]:
            - generic [ref=e67]:
              - generic [ref=e68]:
                - paragraph [ref=e69]: Занятие 15103 · 29 июля
                - generic [ref=e70]: Устная E2E firefox
              - generic [ref=e71]:
                - generic [ref=e72]: Только условие
                - button "Ответить на все задачи" [ref=e73]
            - paragraph [ref=e74]:
              - img [ref=e75]
              - text: 4 задачи в листке
          - article [ref=e78]:
            - generic [ref=e79]:
              - region "Задача 15103н.1. «Устная E2E firefox»" [ref=e80]:
                - generic [ref=e81]:
                  - heading "Задача 15103н.1. «Устная E2E firefox»" [level=2] [ref=e82]:
                    - text: Задача 15103н.1.
                    - generic [ref=e83]: «Устная E2E firefox»
                  - generic [ref=e84]:
                    - generic [ref=e85]: Не начата
                    - button "Открыть задачу 1" [ref=e86]:
                      - text: Открыть
                      - img
                - paragraph [ref=e87]: Условие открываемой задачи 1.
                - generic [ref=e90]:
                  - button "Ответить" [ref=e91]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e92]:
                    - button "Задать вопрос" [ref=e93]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15103н.2. «Выдача задачи 2»" [ref=e94]:
                - generic [ref=e95]:
                  - heading "Задача 15103н.2. «Выдача задачи 2»" [level=2] [ref=e96]:
                    - text: Задача 15103н.2.
                    - generic [ref=e97]: «Выдача задачи 2»
                  - generic [ref=e98]:
                    - generic [ref=e99]: Не начата
                    - button "Открыть задачу 2" [ref=e100]:
                      - text: Открыть
                      - img
                - paragraph [ref=e101]: Условие открываемой задачи 2.
                - generic [ref=e104]:
                  - button "Ответить" [ref=e105]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e106]:
                    - button "Задать вопрос" [ref=e107]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15103н.3. «Выдача задачи 3»" [ref=e108]:
                - generic [ref=e109]:
                  - heading "Задача 15103н.3. «Выдача задачи 3»" [level=2] [ref=e110]:
                    - text: Задача 15103н.3.
                    - generic [ref=e111]: «Выдача задачи 3»
                  - generic [ref=e112]:
                    - generic [ref=e113]: Не начата
                    - button "Открыть задачу 3" [ref=e114]:
                      - text: Открыть
                      - img
                - paragraph [ref=e115]: Условие открываемой задачи 3.
                - generic [ref=e118]:
                  - button "Ответить" [ref=e119]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e120]:
                    - button "Задать вопрос" [ref=e121]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15103н.4. «Выдача задачи 4»" [ref=e122]:
                - generic [ref=e123]:
                  - heading "Задача 15103н.4. «Выдача задачи 4»" [level=2] [ref=e124]:
                    - text: Задача 15103н.4.
                    - generic [ref=e125]: «Выдача задачи 4»
                  - generic [ref=e126]:
                    - generic [ref=e127]: Не начата
                    - button "Открыть задачу 4" [ref=e128]:
                      - text: Открыть
                      - img
                - paragraph [ref=e129]: Условие открываемой задачи 4.
                - generic [ref=e132]:
                  - button "Ответить" [ref=e133]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e134]:
                    - button "Задать вопрос" [ref=e135]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15103н.5. «Выдача задачи 5»" [ref=e136]:
                - generic [ref=e137]:
                  - heading "Задача 15103н.5. «Выдача задачи 5»" [level=2] [ref=e138]:
                    - text: Задача 15103н.5.
                    - generic [ref=e139]: «Выдача задачи 5»
                  - generic [ref=e140]:
                    - generic [ref=e141]: Не начата
                    - button "Открыть задачу 5" [ref=e142]:
                      - text: Открыть
                      - img
                - paragraph [ref=e143]: Условие открываемой задачи 5.
                - generic [ref=e146]:
                  - button "Ответить" [ref=e147]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e148]:
                    - button "Задать вопрос" [ref=e149]:
                      - img
                      - text: Задать вопрос
  - generic:
    - region "Notifications"
```

# Test source

```ts
  1   | import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
  2   | import { expect, test } from './fixtures'
  3   |
  4   | // docs/problem-release.md: three live readers, real aiohttp, no page reload.
  5   | test('teacher releases fifteen tasks progressively to Student and Family', async ({
  6   |   page,
  7   |   secondaryContext,
  8   | }, testInfo) => {
  9   |   test.setTimeout(120_000)
  10  |   const lesson = { chromium: 15101, webkit: 15102, firefox: 15103 }[testInfo.project.name]!
  11  |   const student = await secondaryContext.newPage()
  12  |   const family = await secondaryContext.newPage()
  13  |   await loginThroughUi(student, AUTH_PERSONAS.student, `/student/tasks/math-5-7/н/${lesson}`)
  14  |   await loginThroughUi(family, AUTH_PERSONAS.family, `/family/tasks/math-5-7/н/${lesson}`)
  15  |   await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/gl-${lesson}`)
  16  |   const workflow = page.getByTestId('content-workflow-condition')
  17  |   const load = workflow.getByRole('button', { name: 'Показать PWA и Telegram' })
  18  |   await load.click()
  19  |   const controls = page.getByRole('region', { name: 'Позадачная публикация' })
  20  |   await expect(controls).toBeVisible()
  21  |   await expect(workflow.getByRole('switch')).toHaveCount(15)
  22  |   await expect(workflow.getByRole('alert')).toHaveCount(0)
  23  |   const studentTasks = student.getByRole('heading', { name: /^Задача / })
  24  |   const familyTasks = family.getByRole('heading', { name: /^Задача / })
  25  |   await expect(studentTasks).toHaveCount(15)
  26  |   await expect(familyTasks).toHaveCount(15)
  27  |   const navigations: string[] = []
  28  |   student.on('framenavigated', (frame) => {
  29  |     if (frame === student.mainFrame()) navigations.push(frame.url())
  30  |   })
  31  |   family.on('framenavigated', (frame) => {
  32  |     if (frame === family.mainFrame()) navigations.push(frame.url())
  33  |   })
  34  |   await controls.getByRole('button', { name: 'Закрыть все' }).click()
  35  |   await expect(student.getByText('Задачи скоро откроются.', { exact: true })).toBeVisible()
  36  |   await expect(family.getByText('Задачи скоро откроются.', { exact: true })).toBeVisible()
  37  |   await expect(studentTasks).toHaveCount(0)
  38  |   await expect(familyTasks).toHaveCount(0)
  39  |   await student.screenshot({ path: testInfo.outputPath('student-waiting.png') })
  40  |   await family.screenshot({ path: testInfo.outputPath('family-waiting.png') })
  41  |   for (const index of [0, 1]) {
  42  |     await workflow.getByRole('switch').nth(index).click()
  43  |     await expect(workflow.getByRole('switch').nth(index)).toBeChecked()
  44  |     await expect(workflow.getByRole('switch').nth(index)).toBeEnabled()
  45  |   }
  46  |   await expect(studentTasks).toHaveCount(2)
  47  |   await expect(familyTasks).toHaveCount(2)
  48  |   await controls.scrollIntoViewIfNeeded()
  49  |   await page.screenshot({ path: testInfo.outputPath('staff-release-preview.png') })
  50  |   await page.screenshot({ path: testInfo.outputPath('staff-two-open.png'), fullPage: true })
  51  |   await student.screenshot({ path: testInfo.outputPath('student-two-open.png'), fullPage: true })
  52  |   await family.screenshot({ path: testInfo.outputPath('family-two-open.png'), fullPage: true })
  53  |   for (const [name, reader] of [
  54  |     ['staff', page],
  55  |     ['student', student],
  56  |     ['family', family],
  57  |   ] as const) {
  58  |     await reader.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  59  |     await reader.screenshot({
  60  |       path: testInfo.outputPath(`${name}-dark-two-open.png`),
  61  |       fullPage: true,
  62  |     })
  63  |     await reader.setViewportSize({ width: 390, height: 844 })
  64  |     await reader.screenshot({
  65  |       path: testInfo.outputPath(`${name}-mobile-two-open.png`),
  66  |       fullPage: true,
  67  |     })
  68  |     await reader.setViewportSize({ width: 1280, height: 720 })
  69  |     await reader.getByRole('button', { name: 'Переключить на светлую тему' }).click()
  70  |   }
  71  |   for (const index of [2, 3, 4]) {
  72  |     await workflow.getByRole('switch').nth(index).click()
  73  |     await expect(workflow.getByRole('switch').nth(index)).toBeChecked()
  74  |     await expect(workflow.getByRole('switch').nth(index)).toBeEnabled()
  75  |   }
  76  |   await expect(studentTasks).toHaveCount(5)
  77  |   await expect(familyTasks).toHaveCount(5)
  78  |   await secondaryContext.setOffline(true)
  79  |   // WebKit/Firefox do not consistently emit browser availability events for
  80  |   // setOffline. Keep real network loss and deliver the same events as a device.
  81  |   for (const reader of [student, family])
  82  |     await reader.evaluate(() => {
  83  |       Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })
  84  |       dispatchEvent(new Event('offline'))
  85  |     })
  86  |   await controls.getByRole('button', { name: 'Открыть все' }).click()
  87  |   await expect(controls.getByRole('status')).toHaveText('Открыто 15 из 15')
  88  |   await expect(studentTasks).toHaveCount(5)
  89  |   await expect(familyTasks).toHaveCount(5)
  90  |   await secondaryContext.setOffline(false)
  91  |   for (const reader of [student, family])
  92  |     await reader.evaluate(() => {
  93  |       Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => true })
  94  |       dispatchEvent(new Event('online'))
  95  |     })
  96  |   await student.bringToFront()
  97  |   await expect.poll(() => student.evaluate(() => document.visibilityState)).toBe('visible')
  98  |   // As in news-notifications.spec.ts, Playwright can foreground a tab without
  99  |   // a visibilitychange; deliver that device event after proving visibility.
  100 |   await student.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
> 101 |   await expect(studentTasks).toHaveCount(15, { timeout: 30_000 })
      |                              ^ Error: expect(locator).toHaveCount(expected) failed
  102 |   await family.bringToFront()
  103 |   await expect.poll(() => family.evaluate(() => document.visibilityState)).toBe('visible')
  104 |   await family.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))
  105 |   await expect(familyTasks).toHaveCount(15, { timeout: 30_000 })
  106 |   // Retraction also reaches already open readers.
  107 |   await workflow.getByRole('switch').nth(0).click()
  108 |   await expect(studentTasks).toHaveCount(14)
  109 |   await expect(familyTasks).toHaveCount(14)
  110 |   await controls.getByRole('button', { name: 'Открыть все' }).click()
  111 |   await expect(studentTasks).toHaveCount(15)
  112 |   await expect(familyTasks).toHaveCount(15)
  113 |   expect(navigations).toEqual([])
  114 | })
  115 |
```
