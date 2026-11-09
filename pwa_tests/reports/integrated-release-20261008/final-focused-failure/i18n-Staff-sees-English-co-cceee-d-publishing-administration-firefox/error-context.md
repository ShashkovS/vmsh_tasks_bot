# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: i18n.spec.ts >> Staff sees English course, classroom, oral, and publishing administration
- Location: e2e/i18n.spec.ts:161:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'Rooms' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByRole('heading', { name: 'Rooms' })

```

```yaml
- region "Notifications"
```

# Test source

```ts
  77  |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  78  |     await expect(page.getByRole('link', { name: 'Problems' }).first()).toBeVisible()
  79  |     await expect(page.getByText('Interface language').first()).toBeVisible()
  80  | 
  81  |     await page.reload()
  82  |     await expect(page.getByRole('link', { name: 'Profile' }).first()).toBeVisible()
  83  | 
  84  |     // A second device gets the account language right after sign-in.
  85  |     const otherPage = await secondaryContext.newPage()
  86  |     await loginThroughUi(otherPage, AUTH_PERSONAS.student, '/student/')
  87  |     await expect(otherPage.locator('html')).toHaveAttribute('lang', 'en')
  88  |     await otherPage.close()
  89  |   } finally {
  90  |     await saveAccountLocale(page, 'student', 'ru')
  91  |   }
  92  | })
  93  | 
  94  | // P3 acceptance: Student home-adjacent routes, support, news and notification
  95  | // preferences use the selected interface language while server-provided names
  96  | // and message bodies remain source data.
  97  | test('Student sees English support, news, progress and notification chrome', async ({ page }) => {
  98  |   await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  99  |   try {
  100 |     await page.getByRole('radio', { name: 'English' }).click()
  101 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  102 | 
  103 |     await page.goto('/student/questions')
  104 |     await expect(page.getByRole('heading', { name: 'Your questions' })).toBeVisible()
  105 | 
  106 |     await page.goto('/student/news')
  107 |     await expect(page.getByRole('heading', { name: 'News' })).toBeVisible()
  108 |     await expect(
  109 |       page.getByText('Posts from Telegram channels and club announcements.'),
  110 |     ).toBeVisible()
  111 | 
  112 |     await page.goto('/student/progress')
  113 |     await expect(page.getByRole('heading', { name: 'Progress' })).toBeVisible()
  114 | 
  115 |     await page.goto('/student/profile/notifications')
  116 |     await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
  117 |     await expect(page.getByRole('heading', { name: 'Categories' })).toBeVisible()
  118 |   } finally {
  119 |     await saveAccountLocale(page, 'student', 'ru')
  120 |   }
  121 | })
  122 | 
  123 | test('Staff switches the language from the header menu', async ({ page }) => {
  124 |   await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  125 |   try {
  126 |     await page.getByRole('button', { name: 'Язык интерфейса' }).click()
  127 |     await page.getByRole('menuitem', { name: 'English' }).click()
  128 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  129 |     await expect(page.getByRole('button', { name: 'Interface language' })).toBeVisible()
  130 |     await expect(page.getByRole('link', { name: 'Overview' }).first()).toBeVisible()
  131 |   } finally {
  132 |     await saveAccountLocale(page, 'staff', 'ru')
  133 |   }
  134 | })
  135 | 
  136 | // P4 acceptance: Staff review, result and statistics chrome follows the account
  137 | // locale, while course, group and person names are still server-provided data.
  138 | test('Staff sees English review, result and statistics controls', async ({ page }) => {
  139 |   await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  140 |   try {
  141 |     await page.getByRole('button', { name: 'Язык интерфейса' }).click()
  142 |     await page.getByRole('menuitem', { name: 'English' }).click()
  143 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  144 | 
  145 |     await page.goto('/staff/review')
  146 |     await expect(page.getByRole('heading', { name: 'Review queue' })).toBeVisible()
  147 | 
  148 |     await page.goto('/staff/student-results')
  149 |     await expect(page.getByRole('heading', { name: 'Student results' })).toBeVisible()
  150 | 
  151 |     await page.goto('/staff/statistics?course=c-1&lesson=41')
  152 |     await expect(page.getByRole('heading', { name: 'Course statistics' })).toBeVisible()
  153 |   } finally {
  154 |     await saveAccountLocale(page, 'staff', 'ru')
  155 |   }
  156 | })
  157 | 
  158 | // P5 acceptance: course administration, rooms, oral windows, local news, and
  159 | // group announcements follow the account locale. Course/group names and
  160 | // authored publication text are server data and intentionally stay unchanged.
  161 | test('Staff sees English course, classroom, oral, and publishing administration', async ({
  162 |   page,
  163 | }) => {
  164 |   await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  165 |   try {
  166 |     await page.getByRole('button', { name: 'Язык интерфейса' }).click()
  167 |     await page.getByRole('menuitem', { name: 'English' }).click()
  168 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  169 | 
  170 |     await page.goto('/staff/courses?tab=catalog')
  171 |     await expect(page.getByRole('heading', { level: 1, name: 'Courses and groups' })).toBeVisible()
  172 | 
  173 |     await page.goto('/staff/courses?tab=schedule')
  174 |     await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible()
  175 | 
  176 |     await page.goto('/staff/classrooms?tab=catalog&roomStatus=active')
> 177 |     await expect(page.getByRole('heading', { name: 'Rooms' })).toBeVisible()
      |                                                                ^ Error: expect(locator).toBeVisible() failed
  178 |     await expect(page.getByRole('heading', { name: 'Room catalog' })).toBeVisible()
  179 | 
  180 |     await page.goto('/staff/oral?groupLesson=gl-921&tab=windows')
  181 |     await expect(page.getByRole('heading', { name: 'Oral session' })).toBeVisible()
  182 |     await expect(page.getByRole('region', { name: 'Configured windows' })).toBeVisible()
  183 | 
  184 |     await page.goto('/staff/news?state=all')
  185 |     await expect(page.getByRole('heading', { level: 1, name: 'News' })).toBeVisible()
  186 |     await expect(page.getByText('New PWA publication', { exact: true })).toBeVisible()
  187 | 
  188 |     await page.goto('/staff/broadcasts')
  189 |     await expect(page.getByRole('heading', { name: 'Mailings' })).toBeVisible()
  190 |   } finally {
  191 |     await saveAccountLocale(page, 'staff', 'ru')
  192 |   }
  193 | })
  194 | 
  195 | // P2 acceptance: interface chrome changes language while child and course data remain source data.
  196 | test('Family sees English child progress and notification settings', async ({ page }) => {
  197 |   await page.context().clearCookies()
  198 |   await loginThroughUi(page, AUTH_PERSONAS.family, '/family/profile')
  199 |   try {
  200 |     await page.getByRole('radio', { name: 'English' }).click()
  201 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  202 | 
  203 |     await page.goto('/family/children')
  204 |     await expect(page.getByRole('heading', { name: 'Children' })).toBeVisible()
  205 |     await page
  206 |       .getByText('Алексей Тестовый-Онлайн')
  207 |       .locator('xpath=../../..')
  208 |       .getByRole('button', { name: 'Open' })
  209 |       .click()
  210 |     await expect(page.getByRole('heading', { name: 'Алексей Тестовый-Онлайн' })).toBeVisible()
  211 |     await expect(page.getByText('Course history', { exact: true })).toBeVisible()
  212 |     await expect(page.getByText(/^Lesson \d+$/, { exact: true }).first()).toBeVisible()
  213 |     await expect(page.getByText(/\d+ of \d+ problems accepted/).first()).toBeVisible()
  214 | 
  215 |     await page.goto('/family/profile/notifications')
  216 |     await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible()
  217 |     await expect(page.getByRole('heading', { name: 'Recent events' })).toBeVisible()
  218 |   } finally {
  219 |     await saveAccountLocale(page, 'family', 'ru')
  220 |   }
  221 | })
  222 | 
  223 | test('English device language translates the sign-in page', async ({ page, context, baseURL }) => {
  224 |   await context.addCookies([{ name: 'vmsh-locale', value: 'en', url: baseURL ?? '' }])
  225 |   await page.goto('/family/login')
  226 |   await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  227 |   await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  228 |   await expect(page.getByLabel('Password', { exact: true })).toBeVisible()
  229 | })
  230 | 
  231 | test('Russian stays the default without a device choice', async ({ page }) => {
  232 |   await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  233 |   await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  234 |   await expect(page.getByText('Активная группа').first()).toBeVisible()
  235 | })
  236 | 
  237 | // P6: content tools change language without translating lesson/course content.
  238 | test('Staff sees English lesson, import, synonym, and whiteboard tools', async ({
  239 |   page,
  240 | }, testInfo) => {
  241 |   await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  242 |   try {
  243 |     await page.getByRole('button', { name: 'Язык интерфейса' }).click()
  244 |     await page.getByRole('menuitem', { name: 'English' }).click()
  245 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  246 |     await page.goto('/staff/lessons')
  247 |     await expect(
  248 |       page.getByRole('heading', { name: 'Lessons and publications', exact: true }),
  249 |     ).toBeVisible()
  250 |     await expect(page.getByRole('button', { name: 'Create class', exact: true })).toBeVisible()
  251 |     await page.goto('/staff/lessons/gl-921')
  252 |     await expect(page.getByText('LaTeX and publications', { exact: true })).toBeVisible()
  253 |     await page.locator('summary').filter({ hasText: 'Block before problems' }).click()
  254 |     const markdown = page.getByRole('textbox', { name: 'Block before problems: Markdown' })
  255 |     await markdown.fill('> ::video[Авторское название](https://youtu.be/dQw4w9WgXcQ)')
  256 |     await expect(page.locator('details').filter({ has: markdown }).getByRole('alert')).toHaveText(
  257 |       'Video is allowed only as a standalone top-level block',
  258 |     )
  259 |     await markdown.fill('Авторский текст **без перевода**')
  260 |     await expect(page.getByRole('region', { name: 'Draft preview', exact: true })).toContainText(
  261 |       'Авторский текст без перевода',
  262 |     )
  263 |     await page.goto('/staff/problems')
  264 |     await expect(page.getByText('XLSX file', { exact: true })).toBeVisible()
  265 |     await page.goto('/staff/problems/synonyms')
  266 |     await expect(page.getByRole('heading', { name: 'Problem synonyms', exact: true })).toBeVisible()
  267 |     await page.goto('/staff/whiteboard-export')
  268 |     await expect(
  269 |       page.getByText('Problem statements as PNG files for Zoom Whiteboard'),
  270 |     ).toBeVisible()
  271 |     await expect(page.getByText('Include statistics', { exact: true })).toBeVisible()
  272 |     await page.screenshot({ path: testInfo.outputPath('p6-whiteboard-en.png'), fullPage: true })
  273 |     await page.setViewportSize({ width: 390, height: 844 })
  274 |     await expect(page.getByRole('button', { name: 'Download ZIP', exact: true })).toBeVisible()
  275 |     await page.screenshot({
  276 |       path: testInfo.outputPath('p6-whiteboard-en-narrow.png'),
  277 |       fullPage: true,
```