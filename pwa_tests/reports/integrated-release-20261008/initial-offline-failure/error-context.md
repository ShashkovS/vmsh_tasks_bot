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
    64 × locator resolved to 5 elements
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
              - img [ref=e9]:
                - generic [ref=e12]: "179"
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
            - generic [ref=e28]: Задачи
          - link "Новости" [ref=e29] [cursor=pointer]:
            - /url: /student/news
            - img [ref=e30]
            - generic [ref=e33]: Новости
          - link "Прогресс" [ref=e34] [cursor=pointer]:
            - /url: /student/progress
            - img [ref=e35]
            - generic [ref=e38]: Прогресс
          - link "Профиль" [ref=e39] [cursor=pointer]:
            - /url: /student/profile
            - img [ref=e40]
            - generic [ref=e43]: Профиль
      - main [ref=e44]:
        - status [ref=e45]:
          - img [ref=e46]
          - generic [ref=e51]:
            - generic [ref=e52]: Восстанавливаем связь…
            - paragraph [ref=e53]: Показана последняя сохранённая копия от 8 окт. 2026 г., 15:19. Новые публикации и изменения появятся после восстановления связи.
        - status [ref=e54]: Задачи всех уровней сохранены
        - generic [ref=e58]:
          - generic [ref=e59]:
            - generic [ref=e60]:
              - generic [ref=e61]:
                - paragraph [ref=e62]: Занятие 15101 · 29 июля
                - generic [ref=e63]: Устная E2E chromium
              - generic [ref=e64]:
                - generic [ref=e65]: Только условие
                - button "Ответить на все задачи" [ref=e66]
            - paragraph [ref=e67]:
              - img [ref=e68]
              - text: 5 задач в листке
          - article [ref=e70]:
            - generic [ref=e71]:
              - region "Задача 15101н.1. «Устная E2E chromium»" [ref=e72]:
                - generic [ref=e73]:
                  - heading "Задача 15101н.1. «Устная E2E chromium»" [level=2] [ref=e74]:
                    - text: Задача 15101н.1.
                    - generic [ref=e75]: «Устная E2E chromium»
                  - generic [ref=e76]:
                    - generic [ref=e77]: Не начата
                    - button "Открыть задачу 1" [ref=e78]:
                      - text: Открыть
                      - img
                - paragraph [ref=e79]: Условие открываемой задачи 1.
                - generic [ref=e82]:
                  - button "Ответить" [ref=e83]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e84]:
                    - button "Задать вопрос" [ref=e85]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15101н.2. «Выдача задачи 2»" [ref=e86]:
                - generic [ref=e87]:
                  - heading "Задача 15101н.2. «Выдача задачи 2»" [level=2] [ref=e88]:
                    - text: Задача 15101н.2.
                    - generic [ref=e89]: «Выдача задачи 2»
                  - generic [ref=e90]:
                    - generic [ref=e91]: Не начата
                    - button "Открыть задачу 2" [ref=e92]:
                      - text: Открыть
                      - img
                - paragraph [ref=e93]: Условие открываемой задачи 2.
                - generic [ref=e96]:
                  - button "Ответить" [ref=e97]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e98]:
                    - button "Задать вопрос" [ref=e99]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15101н.3. «Выдача задачи 3»" [ref=e100]:
                - generic [ref=e101]:
                  - heading "Задача 15101н.3. «Выдача задачи 3»" [level=2] [ref=e102]:
                    - text: Задача 15101н.3.
                    - generic [ref=e103]: «Выдача задачи 3»
                  - generic [ref=e104]:
                    - generic [ref=e105]: Не начата
                    - button "Открыть задачу 3" [ref=e106]:
                      - text: Открыть
                      - img
                - paragraph [ref=e107]: Условие открываемой задачи 3.
                - generic [ref=e110]:
                  - button "Ответить" [ref=e111]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e112]:
                    - button "Задать вопрос" [ref=e113]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15101н.4. «Выдача задачи 4»" [ref=e114]:
                - generic [ref=e115]:
                  - heading "Задача 15101н.4. «Выдача задачи 4»" [level=2] [ref=e116]:
                    - text: Задача 15101н.4.
                    - generic [ref=e117]: «Выдача задачи 4»
                  - generic [ref=e118]:
                    - generic [ref=e119]: Не начата
                    - button "Открыть задачу 4" [ref=e120]:
                      - text: Открыть
                      - img
                - paragraph [ref=e121]: Условие открываемой задачи 4.
                - generic [ref=e124]:
                  - button "Ответить" [ref=e125]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e126]:
                    - button "Задать вопрос" [ref=e127]:
                      - img
                      - text: Задать вопрос
              - region "Задача 15101н.5. «Выдача задачи 5»" [ref=e128]:
                - generic [ref=e129]:
                  - heading "Задача 15101н.5. «Выдача задачи 5»" [level=2] [ref=e130]:
                    - text: Задача 15101н.5.
                    - generic [ref=e131]: «Выдача задачи 5»
                  - generic [ref=e132]:
                    - generic [ref=e133]: Не начата
                    - button "Открыть задачу 5" [ref=e134]:
                      - text: Открыть
                      - img
                - paragraph [ref=e135]: Условие открываемой задачи 5.
                - generic [ref=e138]:
                  - button "Ответить" [ref=e139]:
                    - img
                    - text: Ответить
                    - img
                  - region "Обсуждение задачи" [ref=e140]:
                    - button "Задать вопрос" [ref=e141]:
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