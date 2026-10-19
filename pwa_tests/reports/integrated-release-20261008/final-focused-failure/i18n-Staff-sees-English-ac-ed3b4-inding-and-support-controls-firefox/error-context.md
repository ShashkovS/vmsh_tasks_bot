# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: i18n.spec.ts >> Staff sees English account, access, audit, analytics, binding, and support controls
- Location: e2e/i18n.spec.ts:286:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'Batch account creation' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByRole('heading', { name: 'Batch account creation' })

```

```yaml
- region "Notifications"
```

# Test source

```ts
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
  278 |     })
  279 |   } finally {
  280 |     await saveAccountLocale(page, 'staff', 'ru')
  281 |   }
  282 | })
  283 | 
  284 | // P7 acceptance: administrative controls translate independently from account,
  285 | // course, group, audit and support records returned by the API.
  286 | test('Staff sees English account, access, audit, analytics, binding, and support controls', async ({
  287 |   page,
  288 | }) => {
  289 |   await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  290 |   try {
  291 |     await page.getByRole('button', { name: 'Язык интерфейса' }).click()
  292 |     await page.getByRole('menuitem', { name: 'English' }).click()
  293 |     await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  294 | 
  295 |     await page.goto('/staff/users?tab=imports')
> 296 |     await expect(page.getByRole('heading', { name: 'Batch account creation' })).toBeVisible()
      |                                                                                 ^ Error: expect(locator).toBeVisible() failed
  297 |     await expect(page.getByLabel('Paste rows from a table').first()).toBeVisible()
  298 | 
  299 |     await page.goto('/staff/users?tab=teachers')
  300 |     await expect(page.getByRole('heading', { name: 'Teachers and access' })).toBeVisible()
  301 | 
  302 |     await page.goto('/staff/audit?objectType=all&q=e2e.audit.baseline')
  303 |     await expect(page.getByRole('heading', { name: 'Change log' })).toBeVisible()
  304 |     await expect(page.getByText('e2e.audit.baseline', { exact: true })).toBeVisible()
  305 | 
  306 |     await page.goto('/staff/analytics')
  307 |     await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
  308 | 
  309 |     await page.goto('/staff/courses?tab=telegram')
  310 |     await expect(page.getByLabel('Course or group')).toBeVisible()
  311 |     await expect(page.getByLabel('Purpose')).toBeVisible()
  312 | 
  313 |     await page.goto('/staff/questions?state=awaiting_staff')
  314 |     await expect(page.getByRole('heading', { name: 'Student questions' })).toBeVisible()
  315 |   } finally {
  316 |     await saveAccountLocale(page, 'staff', 'ru')
  317 |   }
  318 | })
  319 | 
```