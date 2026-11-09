# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: review-workspace.spec.ts >> Series feed >> clone, complete, compare, correct and move whole entries
- Location: e2e/review-workspace.spec.ts:140:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('Уточнённый комментарий', { exact: true })
Expected: visible
Error: strict mode violation: getByText('Уточнённый комментарий', { exact: true }) resolved to 2 elements:
    1) <p class="whitespace-pre-wrap rounded-lg border border-border p-3">Уточнённый комментарий</p> aka getByText('Уточнённый комментарий').first()
    2) <p class="whitespace-pre-wrap [overflow-wrap:anywhere]">Уточнённый комментарий</p> aka getByLabel('История переписки и проверок').getByText('Уточнённый комментарий')

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByText('Уточнённый комментарий', { exact: true })

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - banner [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e6]:
          - link "ВМШ 179" [ref=e7] [cursor=pointer]:
            - /url: /staff/
            - generic [ref=e8]:
              - img [ref=e9]:
                - generic [ref=e12]: "179"
              - generic [ref=e13]: ВМШ 179
          - generic "Тестовый Преподаватель" [ref=e14]
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
          - link "Сводка" [ref=e27] [cursor=pointer]:
            - /url: /staff/
            - img [ref=e28]
            - generic [ref=e31]: Сводка
          - link "Проверка" [ref=e32] [cursor=pointer]:
            - /url: /staff/review
            - img [ref=e33]
            - generic [ref=e37]: Проверка
          - link "Вопросы" [ref=e38] [cursor=pointer]:
            - /url: /staff/questions
            - img [ref=e39]
            - generic [ref=e42]: Вопросы
          - link "Очное занятие" [ref=e43] [cursor=pointer]:
            - /url: /staff/in-person
            - img [ref=e44]
            - generic [ref=e48]: Очное занятие
          - link "Zoom-приём" [ref=e49] [cursor=pointer]:
            - /url: /staff/oral
            - img [ref=e50]
            - generic [ref=e53]: Zoom-приём
          - link "Уроки" [ref=e54] [cursor=pointer]:
            - /url: /staff/lessons
            - img [ref=e55]
            - generic [ref=e58]: Уроки
          - link "Материалы для разбора" [ref=e59] [cursor=pointer]:
            - /url: /staff/whiteboard-export
            - img [ref=e60]
            - generic [ref=e63]: Материалы для разбора
          - link "Курсы" [ref=e64] [cursor=pointer]:
            - /url: /staff/courses
            - img [ref=e65]
            - generic [ref=e75]: Курсы
          - link "Новости" [ref=e76] [cursor=pointer]:
            - /url: /staff/news
            - img [ref=e77]
            - generic [ref=e80]: Новости
          - link "Участники" [ref=e81] [cursor=pointer]:
            - /url: /staff/users
            - img [ref=e82]
            - generic [ref=e87]: Участники
          - link "Статистика" [ref=e88] [cursor=pointer]:
            - /url: /staff/statistics
            - img [ref=e89]
            - generic [ref=e91]: Статистика
      - main [ref=e92]:
        - navigation "Проверки" [ref=e93]:
          - link "Очередь" [ref=e94] [cursor=pointer]:
            - /url: /staff/review
          - link "Проверено" [ref=e95] [cursor=pointer]:
            - /url: /staff/review/history
          - link "Исправить последнюю" [ref=e96] [cursor=pointer]:
            - /url: /staff/review/history?review=r-7
        - generic [ref=e97]:
          - heading "9751н.1 · E2E проверка series-chromium" [level=1] [ref=e98]
          - group [ref=e99]:
            - generic "Условие задачи" [ref=e100] [cursor=pointer]
            - paragraph [ref=e101]: Условие проверяемой версии недоступно.
          - button "Показать предыдущие 20 проверок" [ref=e102]
          - generic [ref=e103]:
            - link "К списку задач" [ref=e104] [cursor=pointer]:
              - /url: /staff/review
            - button "Исправить предыдущую · ⌘/Ctrl + Alt + ←" [ref=e105]
            - button "Дальше · ⌘/Ctrl + Alt + →" [ref=e106]
          - article [ref=e107]:
            - generic [ref=e109]:
              - heading "Второй series-chromium · 9751н.1 · Зачтено" [level=2] [ref=e110]
              - article [ref=e111]:
                - paragraph [ref=e112]: Второе решение для сравнения
                - img "Страница решения 1" [ref=e113]
              - paragraph [ref=e114]: Уточнённый комментарий
              - group [ref=e115]:
                - generic "История переписки и проверок" [ref=e116]
                - region "История переписки и проверок" [ref=e117]:
                  - list [ref=e118]:
                    - listitem [ref=e119]:
                      - generic [ref=e120]:
                        - generic [ref=e121]:
                          - generic [ref=e122]: series-chromium Второй
                          - time [ref=e123]: 28.07.2026, 15:00:00
                        - generic [ref=e124]:
                          - generic [ref=e126]: Посылка / сообщение · Приложение · 9751н.1
                          - paragraph [ref=e127]: Второе решение для сравнения
                          - link "Открыть вложение" [ref=e129] [cursor=pointer]:
                            - /url: /staff/api/v1/review/history/r-7/attachments/sa-9904
                            - img "Вложение к посылке" [ref=e130]
                    - listitem [ref=e131]:
                      - generic [ref=e132]:
                        - generic [ref=e133]:
                          - generic [ref=e134]: Система
                          - time [ref=e135]: 08.10.2026, 16:14:29
                        - generic [ref=e136]:
                          - generic [ref=e138]: Посылка / сообщение · Система · 9751н.1
                          - paragraph [ref=e139]: Скопировано преподавателем в задачу 9751н.2 · Цель серии.
                    - listitem [ref=e140]:
                      - generic [ref=e141]:
                        - generic [ref=e142]:
                          - generic [ref=e143]: Преподаватель Тестовый
                          - time [ref=e144]: 08.10.2026, 16:14:29
                        - generic [ref=e145]:
                          - generic [ref=e146]:
                            - generic [ref=e147]: Проверка · Преподаватель · 9751н.1
                            - generic "Зачтено" [ref=e148]:
                              - generic [ref=e149]: +
                              - generic [ref=e150]: Зачтено
                          - paragraph [ref=e151]: Сравниваем решения chromium
                    - listitem [ref=e152]:
                      - generic [ref=e153]:
                        - generic [ref=e154]:
                          - generic [ref=e155]: Преподаватель Тестовый
                          - time [ref=e156]: 08.10.2026, 16:14:29
                        - generic [ref=e157]:
                          - generic [ref=e158]:
                            - generic [ref=e159]: Проверка · Преподаватель · 9751н.1
                            - generic "Зачтено" [ref=e160]:
                              - generic [ref=e161]: +
                              - generic [ref=e162]: Зачтено
                          - paragraph [ref=e163]: Уточнённый комментарий
            - button "Перепроверить" [active] [ref=e164]
          - generic [ref=e166]:
            - generic [ref=e167]:
              - generic [ref=e168]:
                - generic [ref=e169]: 9751н.1 · E2E проверка series-chromium
                - heading "Проверка работы" [level=1] [ref=e170]
                - generic [ref=e171]: Тестовый-Онлайн Алексей · Математика 5–7 · Начинающие
              - button "Отказаться от проверки" [ref=e173]
            - generic [ref=e175]:
              - region "Ветки задачи" [ref=e176]:
                - generic [ref=e178]: 9751н.1 · Начинающие
              - region "Работа и обсуждение" [ref=e179]:
                - generic [ref=e181]:
                  - heading "Работа и переписка" [level=2] [ref=e184]
                  - generic [ref=e185]:
                    - generic [ref=e186]:
                      - generic [ref=e187]: 2 сообщений
                      - generic [ref=e188]: Взята вами
                    - list [ref=e190]:
                      - listitem [ref=e191]:
                        - generic [ref=e192]:
                          - generic [ref=e193]:
                            - generic [ref=e194]: Преподаватель
                            - time [ref=e195]: 28 июл., 15:00
                            - generic [ref=e196]:
                              - img [ref=e197]
                              - text: в приложении
                          - paragraph [ref=e199]: Математика 5–7 · Начинающие · 9751н.1
                          - paragraph [ref=e202]: Поясните, почему этот переход верен.
                      - listitem [ref=e203]:
                        - generic [ref=e204]:
                          - generic [ref=e205]:
                            - generic [ref=e206]: Тестовый-Онлайн Алексей
                            - time [ref=e207]: 28 июл., 15:02
                            - generic [ref=e208]:
                              - img [ref=e209]
                              - text: в приложении
                          - paragraph [ref=e211]: Математика 5–7 · Начинающие · 9751н.1
                          - generic [ref=e212]:
                            - generic [ref=e213]:
                              - paragraph [ref=e214]: Я дописал объяснение перехода и проверил крайний случай.
                              - 'region "Разметка: Страница решения 1" [ref=e216]':
                                - toolbar "Инструменты разметки" [ref=e217]:
                                  - button "Карандаш" [pressed] [ref=e218]:
                                    - img
                                  - button "Ластик" [ref=e219]:
                                    - img
                                  - button "Текст" [ref=e220]:
                                    - img
                                  - button "Стрелка" [ref=e221]:
                                    - img
                                  - button "Прямоугольник" [ref=e222]:
                                    - img
                                  - button "Выделение" [ref=e223]:
                                    - img
                                  - button "Красный" [pressed] [ref=e225]
                                  - button "Синий" [ref=e227]
                                  - button "Графитовый" [ref=e229]
                                  - button "Янтарный" [ref=e231]
                                  - button "Отменить" [disabled]:
                                    - img
                                  - button "Повторить" [disabled]:
                                    - img
                                  - button "Повернуть против часовой стрелки" [ref=e234]:
                                    - img
                                  - button "Повернуть по часовой стрелке" [ref=e235]:
                                    - img
                                  - button "Очистить разметку" [disabled]:
                                    - img
                                - region "Страница решения 1; область можно прокручивать после увеличения" [ref=e236]:
                                  - generic [ref=e238]:
                                    - img "Страница решения 1"
                                    - application "Область разметки фотографии" [ref=e239]
                                - generic [ref=e240]:
                                  - button "Уменьшить масштаб" [disabled]:
                                    - img
                                  - button "Увеличить масштаб" [ref=e241]:
                                    - img
                                  - button "Сбросить масштаб" [disabled]:
                                    - img
                                  - generic [ref=e242]: 100% · 0° · 0 пометок
                            - generic [ref=e244]:
                              - button "Перенести в другую задачу" [ref=e245]
                              - button "Клонировать в другую задачу" [ref=e246]
                - generic [ref=e248]:
                  - generic [ref=e249]:
                    - generic [ref=e250]: Комментарий
                    - textbox "Комментарий" [ref=e251]:
                      - /placeholder: Что получилось, что стоит поправить…
                      - text: Черновик второй работы
                  - generic [ref=e252]:
                    - group [ref=e253]:
                      - button "1 Зачтено" [ref=e254]:
                        - generic [ref=e255]: "1"
                        - generic "Зачтено" [ref=e256]:
                          - generic [ref=e257]: +
                          - generic [ref=e258]: Зачтено
                      - button "2 Зачтено с недочётами" [ref=e259]:
                        - generic [ref=e260]: "2"
                        - generic "Зачтено с недочётами" [ref=e261]:
                          - generic [ref=e262]: +.
                          - generic [ref=e263]: Зачтено с недочётами
                      - button "3 В целом верно" [ref=e264]:
                        - generic [ref=e265]: "3"
                        - generic "В целом верно" [ref=e266]:
                          - generic [ref=e267]: ±
                          - generic [ref=e268]: В целом верно
                      - button "4 Половина" [ref=e269]:
                        - generic [ref=e270]: "4"
                        - generic "Половина" [ref=e271]:
                          - generic [ref=e272]: +/2
                          - generic [ref=e273]: Половина
                      - button "5 Есть идеи, не доведено" [ref=e274]:
                        - generic [ref=e275]: "5"
                        - generic "Есть идеи, не доведено" [ref=e276]:
                          - generic [ref=e277]: ∓
                          - generic [ref=e278]: Есть идеи, не доведено
                      - button "6 Есть простая идея" [ref=e279]:
                        - generic [ref=e280]: "6"
                        - generic "Есть простая идея" [ref=e281]:
                          - generic [ref=e282]: −.
                          - generic [ref=e283]: Есть простая идея
                      - button "7 Отклонено" [ref=e284]:
                        - generic [ref=e285]: "7"
                        - generic "Отклонено" [ref=e286]:
                          - generic [ref=e287]: −
                          - generic [ref=e288]: Отклонено
                    - paragraph [ref=e289]: "Клавиши 1–7: от лучшего к худшему, 1 — «+». Не срабатывают в поле ввода."
                  - generic [ref=e290]:
                    - paragraph [ref=e291]: Внутренняя пометка (не видна ученику)
                    - group "Внутренняя пометка (не видна ученику)" [ref=e292]:
                      - button "Суперское решение." [ref=e293]:
                        - generic [ref=e294]: 🔥
                        - generic [ref=e295]: Суперское решение.
                      - button "Жуткая муть." [ref=e296]:
                        - generic [ref=e297]: 😕
                        - generic [ref=e298]: Жуткая муть.
                      - button "Решение, вероятно, списано." [ref=e299]:
                        - generic [ref=e300]: 😠
                        - generic [ref=e301]: Решение, вероятно, списано.
                      - button "Решение, вероятно, от нейросети." [ref=e302]:
                        - generic [ref=e303]: 🤖
                        - generic [ref=e304]: Решение, вероятно, от нейросети.
                    - paragraph [ref=e305]: ⌘/Ctrl + ⌥/Alt + 1–4 · Работает и в комментарии; не видна ученику и родителю.
                  - button "Отправить вердикт" [disabled]
                  - paragraph [ref=e306]: ⌘/Ctrl + Enter — отправить вердикт. Работает и в комментарии.
  - generic:
    - region "Notifications"
```

# Test source

```ts
  74  |   await expect(studentGrade('✅\\+')).toBeVisible()
  75  |   await expect(familyGrade('✅+')).toBeVisible()
  76  |   const manual = await page.evaluate(
  77  |     async ({ id, problemId }) => {
  78  |       const post = async (path: string, body: unknown) => {
  79  |         const response = await fetch(`/staff/api/v1/live-marking/${path}`, {
  80  |           method: 'POST',
  81  |           headers: { 'Content-Type': 'application/json' },
  82  |           body: JSON.stringify(body),
  83  |         })
  84  |         return { status: response.status, body: (await response.json()) as Record<string, unknown> }
  85  |       }
  86  |       const session = await post('sessions', { courseId: 'c-1', sessionId: crypto.randomUUID() })
  87  |       if (session.status !== 200) throw new Error(JSON.stringify(session))
  88  |       const context = {
  89  |         mode: 'zoom',
  90  |         contextId: session.body.sessionId,
  91  |         studentId: 'u-101',
  92  |         lessonId: `gl-${id}`,
  93  |       }
  94  |       const query = new URLSearchParams(context as Record<string, string>)
  95  |       const response = await fetch(`/staff/api/v1/live-marking/cells?${query}`)
  96  |       const cells = (await response.json()) as {
  97  |         cells: Array<{ problemId: string; version: number }>
  98  |       }
  99  |       const cell = cells.cells.find((c) => c.problemId === problemId)
  100 |       if (!cell) throw new Error('Written result missing from Zoom cell projection')
  101 |       const mark = await post('operations', {
  102 |         kind: 'mark',
  103 |         operationId: crypto.randomUUID(),
  104 |         context,
  105 |         studentId: 'u-101',
  106 |         problemId,
  107 |         expectedVersion: cell.version,
  108 |         value: 'minus',
  109 |       })
  110 |       return { ...mark, context }
  111 |     },
  112 |     { id, problemId },
  113 |   )
  114 |   expect(manual.status).toBe(200)
  115 |   await expect(studentGrade('🟥−')).toBeVisible()
  116 |   await expect(familyGrade('🟥−')).toBeVisible()
  117 |   const undo = await page.evaluate(
  118 |     async ({ context, targetOperationId }) => {
  119 |       const response = await fetch('/staff/api/v1/live-marking/operations', {
  120 |         method: 'POST',
  121 |         headers: { 'Content-Type': 'application/json' },
  122 |         body: JSON.stringify({
  123 |           kind: 'undo',
  124 |           operationId: crypto.randomUUID(),
  125 |           context,
  126 |           targetOperationId,
  127 |         }),
  128 |       })
  129 |       return response.status
  130 |     },
  131 |     { context: manual.context, targetOperationId: manual.body.operationId },
  132 |   )
  133 |   expect(undo).toBe(200)
  134 |   await expect(studentGrade('✅\\+')).toBeVisible()
  135 |   await expect(familyGrade('✅+')).toBeVisible()
  136 | })
  137 | 
  138 | test.describe('Series feed', () => {
  139 |   test.describe.configure({ retries: 0 })
  140 |   test('clone, complete, compare, correct and move whole entries', async ({ page }, testInfo) => {
  141 |     // docs/serial-review-feed.md: real SQLite, media and correction editor in all engines.
  142 |     test.setTimeout(120_000)
  143 |     const id = reviewFixtureId(testInfo.project.name) + 50
  144 |     const target = `p-${id + 100}`
  145 |     const comment = page
  146 |       .getByRole('textbox', { name: 'Комментарий', exact: true })
  147 |       .and(page.locator(':enabled'))
  148 |     await loginThroughUi(page, AUTH_PERSONAS.teacher, `/staff/review/series/p-${id}`)
  149 |     await expect(
  150 |       page.getByRole('heading', { level: 1, name: new RegExp(`^${id}н.1`) }),
  151 |     ).toBeVisible()
  152 |     await page.getByText('Условие задачи', { exact: true }).click()
  153 |     await expect(page.getByText('Условие проверяемой версии недоступно.')).toBeVisible()
  154 |     await page.getByRole('button', { name: 'Клонировать в другую задачу', exact: true }).click()
  155 |     await page.getByLabel('Целевая задача').selectOption(target)
  156 |     const clone = page.waitForResponse(
  157 |       (r) => r.url().endsWith('/transfer') && r.request().method() === 'POST',
  158 |     )
  159 |     await page.getByRole('button', { name: 'Клонировать посылку', exact: true }).click()
  160 |     expect((await clone).status()).toBe(200)
  161 |     const firstComment = `Сравниваем решения ${testInfo.project.name}`
  162 |     await comment.fill(firstComment)
  163 |     await page.getByRole('button', { name: '1 Зачтено', exact: true }).click()
  164 |     await comment.press('Control+Enter')
  165 |     await expect(page.getByRole('button', { name: 'Перепроверить', exact: true })).toHaveCount(1)
  166 |     await expect(page.getByText(firstComment, { exact: true })).toBeVisible()
  167 |     await comment.fill('Черновик второй работы')
  168 |     await page.getByRole('button', { name: 'Перепроверить', exact: true }).click()
  169 |     // Current card remains mounted with disabled controls; only correction accepts input.
  170 |     await expect(comment).toHaveValue(firstComment)
  171 |     await comment.fill('Уточнённый комментарий')
  172 |     await comment.press('Control+Enter')
  173 |     await expect(comment).toHaveValue('Черновик второй работы')
> 174 |     await expect(page.getByText('Уточнённый комментарий', { exact: true })).toBeVisible()
      |                                                                             ^ Error: expect(locator).toBeVisible() failed
  175 |     await page.getByRole('button', { name: 'Перенести в другую задачу', exact: true }).click()
  176 |     await page.getByLabel('Целевая задача').selectOption(target)
  177 |     const move = page.waitForResponse(
  178 |       (r) => r.url().endsWith('/transfer') && r.request().method() === 'POST',
  179 |     )
  180 |     await page.getByRole('button', { name: 'Перенести посылку', exact: true }).click()
  181 |     expect((await move).status()).toBe(200)
  182 |     await expect(page.getByText('Доступных работ по этой задаче больше нет')).toBeVisible()
  183 |     await expect(page.getByText(new RegExp(`Перенесено в ${id}н.2`))).toBeVisible()
  184 |     await page.getByRole('button', { name: 'Показать предыдущие 20 проверок' }).click()
  185 |     await expect(page.getByRole('button', { name: 'Перепроверить', exact: true })).toHaveCount(1)
  186 |     await page.goto(`/staff/review/series/${target}`)
  187 |     for (let index = 0; index < 2; index++) {
  188 |       await comment.fill(`Целевая проверка ${index}`)
  189 |       await page.getByRole('button', { name: '1 Зачтено', exact: true }).click()
  190 |       await comment.press('Control+Enter')
  191 |       await expect(page.getByRole('button', { name: 'Перепроверить', exact: true })).toHaveCount(
  192 |         index + 1,
  193 |       )
  194 |     }
  195 |     await expect(page.getByText('Доступных работ по этой задаче больше нет')).toBeVisible()
  196 |     await loginThroughUi(page, AUTH_PERSONAS.student, '/student/')
  197 |     const response = await page.request.get(`/student/api/v1/problems/${target}/thread`)
  198 |     expect(response.status()).toBe(200)
  199 |     const thread = writtenThreadResponseSchema.parse(await response.json()).thread
  200 |     expect(thread?.reviews).toHaveLength(1)
  201 |     expect(
  202 |       thread?.entries.some(
  203 |         (e) => e.authorKind === 'system' && e.text?.includes('преподавателем из задачи'),
  204 |       ),
  205 |     ).toBe(true)
  206 |   })
  207 | })
  208 | 
  209 | test('Phase 6: Staff review restores its draft and completes one leased case', async ({
  210 |   page,
  211 |   secondaryContext,
  212 | }, testInfo) => {
  213 |   test.setTimeout(90_000)
  214 |   const project = testInfo.project.name
  215 |   const fixtureId = reviewFixtureId(project)
  216 |   const queueId = `wq-${fixtureId}`
  217 |   const problemId = `p-${fixtureId}`
  218 |   const studentEntryId = `se-${fixtureId * 10 + 2}`
  219 |   const attachmentId = `sa-${fixtureId}`
  220 |   const title = `E2E проверка ${project}`
  221 | 
  222 |   await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/review')
  223 |   await page.getByRole('button', { name: 'Все работы' }).click()
  224 |   const row = page.getByRole('row').filter({ hasText: title })
  225 |   await expect(row).toBeVisible()
  226 |   // The queue-navigation scenario can leave this teacher's series lease alive.
  227 |   // Release it explicitly before proving a new claim and its realtime update.
  228 |   await row.getByRole('button', { name: 'Открыть' }).click()
  229 |   await page.getByRole('button', { name: 'Отказаться от проверки', exact: true }).click()
  230 |   await expect(row).toBeVisible()
  231 | 
  232 |   // A second Staff account keeps the queue open. Claim and completion must
  233 |   // update it through the audience-scoped queue invalidations, not polling.
  234 |   const adminPage = await secondaryContext.newPage()
  235 |   await loginThroughUi(adminPage, AUTH_PERSONAS.admin, '/staff/review')
  236 |   await adminPage.getByRole('button', { name: 'Все работы' }).click()
  237 |   const adminRow = adminPage.getByRole('row').filter({ hasText: title })
  238 |   await expect(adminRow.getByRole('button', { name: 'Открыть' })).toBeVisible()
  239 | 
  240 |   await row.getByRole('button', { name: 'Открыть' }).click()
  241 |   await expect(page).toHaveURL(new RegExp(`/staff/review/${queueId}\\?`))
  242 |   await expect(adminRow).toContainText('Проверяет Преподаватель Тестовый')
  243 | 
  244 |   await expect(page.getByText('Поясните, почему этот переход верен.')).toBeVisible()
  245 |   await expect(
  246 |     page.getByText('Я дописал объяснение перехода и проверил крайний случай.'),
  247 |   ).toBeVisible()
  248 | 
  249 |   const drawing = page.getByRole('application', { name: 'Область разметки фотографии' })
  250 |   await expect(drawing).toBeVisible()
  251 |   await page.getByRole('button', { name: 'Прямоугольник' }).click()
  252 |   await drawing.scrollIntoViewIfNeeded()
  253 |   const bounds = await drawing.boundingBox()
  254 |   if (!bounds) throw new Error('Review annotation canvas has no visible bounds')
  255 |   await page.mouse.move(bounds.x + bounds.width * 0.2, bounds.y + bounds.height * 0.2)
  256 |   await page.mouse.down()
  257 |   await page.mouse.move(bounds.x + bounds.width * 0.65, bounds.y + bounds.height * 0.45, {
  258 |     steps: 10,
  259 |   })
  260 |   await page.mouse.up()
  261 |   await expect(page.getByText('100% · 0° · 1 пометок')).toBeVisible()
  262 |   // Keyboard activation is stable after the SVG drag releases pointer capture.
  263 |   await page.getByRole('button', { name: 'Повернуть по часовой стрелке' }).focus()
  264 |   await page.keyboard.press('Enter')
  265 |   await expect(page.getByText('100% · 90° · 1 пометок')).toBeVisible()
  266 | 
  267 |   const comment = page.getByLabel('Комментарий')
  268 |   await comment.fill(`Проверено в ${project}; переход обоснован.`)
  269 |   const verdict = page.getByRole('button', { name: /В целом верно/ })
  270 |   await verdict.click()
  271 |   const reaction = page.getByRole('button', { name: /Суперское решение/ })
  272 |   await reaction.click()
  273 | 
  274 |   await page.reload()
```