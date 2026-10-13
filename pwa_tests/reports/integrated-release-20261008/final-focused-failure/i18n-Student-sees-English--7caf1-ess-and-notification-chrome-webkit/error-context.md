# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: i18n.spec.ts >> Student sees English support, news, progress and notification chrome
- Location: e2e/i18n.spec.ts:97:1

# Error details

```
Error: page.goto: Frame load interrupted
Call log:
  - navigating to "http://127.0.0.1:5380/student/questions", waiting until "load"

```

# Page snapshot

```yaml
- main [ref=e3]:
  - status [ref=e5]:
    - img [ref=e6]
    - generic [ref=e8]:
      - heading "Checking the connection" [level=1] [ref=e9]
      - paragraph [ref=e10]: Connecting your account to the server.
```

# Test source

```ts
  3   | 
  4   | // Each journey visits several routes and can reload after an account locale change.
  5   | test.setTimeout(60_000)
  6   | 
  7   | // P8: pre-login device preference, metadata and catalog-independent recovery.
  8   | test('Landing follows the device language and keeps Russian as the default', async ({
  9   |   page,
  10  | }, info) => {
  11  |   await page.goto('/')
  12  |   await expect(page.getByText('Кабинет школьника', { exact: true })).toBeVisible()
  13  |   await page.context().addCookies([{ name: 'vmsh-locale', value: 'en', url: page.url() }])
  14  |   await page.reload()
  15  |   await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  16  |   await expect(page.getByText('Student account', { exact: true })).toBeVisible()
  17  |   await expect(page.getByText('Family account', { exact: true })).toBeVisible()
  18  |   await expect(page).toHaveTitle('VMSh 179 — math circle')
  19  |   await expect(page.locator('meta[name="description"]')).toHaveAttribute(
  20  |     'content',
  21  |     /students and parents/,
  22  |   )
  23  |   await page.screenshot({ path: info.outputPath('p8-landing-en.png'), fullPage: true })
  24  |   await page.setViewportSize({ width: 390, height: 844 })
  25  |   await page.screenshot({ path: info.outputPath('p8-landing-en-narrow.png'), fullPage: true })
  26  |   await expect(page.getByRole('link', { name: 'Open account' }).first()).toHaveAttribute(
  27  |     'href',
  28  |     '/student/',
  29  |   )
  30  | })
  31  | 
  32  | test('Landing recovers from missing catalogs with a bilingual reload screen', async ({ page }) => {
  33  |   let catalogsAvailable = false
  34  |   await page.route('**/catalog-*.js', (route) =>
  35  |     catalogsAvailable
  36  |       ? route.continue()
  37  |       : route.fulfill({
  38  |           status: 503,
  39  |           contentType: 'text/javascript',
  40  |           headers: { 'cache-control': 'no-store' },
  41  |           body: '',
  42  |         }),
  43  |   )
  44  |   await page.goto('/')
  45  |   await expect(page.getByRole('alert')).toContainText('Could not load the interface')
  46  |   await expect(page.getByRole('alert')).toContainText('Не удалось загрузить интерфейс')
  47  |   catalogsAvailable = true
  48  |   await page.getByRole('button', { name: 'Обновить · Reload' }).click()
  49  |   await expect(page.getByText('Кабинет школьника', { exact: true })).toBeVisible()
  50  | })
  51  | 
  52  | // English interface: dev/development-plan/24-i18n.md, docs/i18n.md.
  53  | // The account language is saved from the personal cabinet (Staff: header menu),
  54  | // the page reloads in it, and a new device picks it up at sign-in. Fixture
  55  | // accounts are shared by all specs, so every test restores Russian.
  56  | 
  57  | async function saveAccountLocale(page: Page, audience: string, locale: 'ru' | 'en') {
  58  |   // Account changes can reload the document. Context-level cleanup survives
  59  |   // that navigation and still uses the real audience session and origin check.
  60  |   const response = await page.request.put(`/${audience}/api/v1/auth/locale`, {
  61  |     headers: { Origin: new URL(page.url()).origin },
  62  |     data: { locale },
  63  |   })
  64  |   expect(response.status()).toBe(200)
  65  | }
  66  | 
  67  | test('Student switches the account to English in the profile', async ({
  68  |   page,
  69  |   secondaryContext,
  70  | }) => {
  71  |   await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  72  |   try {
  73  |     await Promise.all([
  74  |       page.waitForEvent('load'),
  75  |       page.getByRole('radio', { name: 'English' }).click(),
  76  |     ])
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
> 103 |     await page.goto('/student/questions')
      |                ^ Error: page.goto: Frame load interrupted
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
  177 |     await expect(page.getByRole('heading', { name: 'Rooms' })).toBeVisible()
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
```