# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: i18n.spec.ts >> Student switches the account to English in the profile
- Location: e2e/i18n.spec.ts:67:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('[data-product="student"]')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for locator('[data-product="student"]')

```

```yaml
- main:
  - status:
    - heading "Сервер не отвечает" [level=1]
    - paragraph: Пробуем подключиться автоматически. Можно продолжать работу с черновиком.
```

# Test source

```ts
  1   | import credentialFixture from '../../pwa_tests/fixtures/auth-credentials-v1.json' with { type: 'json' }
  2   | 
  3   | import { expect, type Page } from './fixtures'
  4   | 
  5   | export type AuthAudience = 'student' | 'family' | 'staff'
  6   | export type AuthPersonaName = 'student' | 'studentInPerson' | 'family' | 'teacher' | 'admin'
  7   | 
  8   | export interface AuthPersona {
  9   |   persona: AuthPersonaName
  10  |   accountPublicId: string
  11  |   audience: AuthAudience
  12  |   username: string
  13  |   credentialField: 'telegramToken' | 'password'
  14  |   credential: string
  15  | }
  16  | 
  17  | const expectedPersonas: AuthPersonaName[] = [
  18  |   'student',
  19  |   'studentInPerson',
  20  |   'family',
  21  |   'teacher',
  22  |   'admin',
  23  | ]
  24  | 
  25  | function parseFixture(): Record<AuthPersonaName, AuthPersona> {
  26  |   if (
  27  |     credentialFixture.fixture !== 'synthetic-auth-credentials-v1' ||
  28  |     credentialFixture.fixtureVersion !== 1
  29  |   ) {
  30  |     throw new Error('Unknown E2E authentication fixture')
  31  |   }
  32  | 
  33  |   const parsed = new Map<AuthPersonaName, AuthPersona>()
  34  |   for (const rawAccount of credentialFixture.accounts) {
  35  |     if (
  36  |       !expectedPersonas.includes(rawAccount.persona as AuthPersonaName) ||
  37  |       !['student', 'family', 'staff'].includes(rawAccount.audience) ||
  38  |       !['telegramToken', 'password'].includes(rawAccount.credentialField) ||
  39  |       !rawAccount.accountPublicId ||
  40  |       !rawAccount.username ||
  41  |       !rawAccount.credential.endsWith('-not-a-secret')
  42  |     ) {
  43  |       throw new Error('Invalid E2E authentication fixture account')
  44  |     }
  45  |     const account = rawAccount as AuthPersona
  46  |     if (
  47  |       parsed.has(account.persona) ||
  48  |       (account.audience === 'student') !== (account.credentialField === 'telegramToken')
  49  |     ) {
  50  |       throw new Error('Ambiguous E2E authentication fixture account')
  51  |     }
  52  |     parsed.set(account.persona, account)
  53  |   }
  54  |   if (parsed.size !== expectedPersonas.length) {
  55  |     throw new Error('Incomplete E2E authentication fixture')
  56  |   }
  57  |   return Object.fromEntries(parsed) as Record<AuthPersonaName, AuthPersona>
  58  | }
  59  | 
  60  | /** Test-only personas. No application or production bundle imports this module. */
  61  | export const AUTH_PERSONAS = parseFixture()
  62  | 
  63  | export function credentialLabel(persona: AuthPersona): string {
  64  |   return persona.credentialField === 'telegramToken' ? 'Токен Telegram-бота' : 'Пароль'
  65  | }
  66  | 
  67  | export async function submitLoginForm(page: Page, persona: AuthPersona): Promise<void> {
  68  |   await page.getByLabel('Логин').fill(persona.username)
  69  |   await page.getByLabel(credentialLabel(persona), { exact: true }).fill(persona.credential)
  70  | 
  71  |   const loginResponse = page.waitForResponse(
  72  |     (response) =>
  73  |       response.request().method() === 'POST' &&
  74  |       new URL(response.url()).pathname === `/${persona.audience}/api/v1/auth/login`,
  75  |   )
  76  |   await page.getByRole('button', { name: 'Войти' }).click()
  77  |   const response = await loginResponse
  78  |   expect(response.status()).toBe(200)
  79  | }
  80  | 
  81  | /**
  82  |  * Complete the real browser login flow through the audience page and aiohttp.
  83  |  * See Phase 1's Playwright acceptance matrix in development-plan/05-phase-1-auth.md.
  84  |  */
  85  | export async function loginThroughUi(
  86  |   page: Page,
  87  |   persona: AuthPersona,
  88  |   intendedRoute = `/${persona.audience}/`,
  89  | ): Promise<void> {
  90  |   const expectedDestination = new URL(intendedRoute, 'http://127.0.0.1:5380')
  91  |   await page.goto(intendedRoute, { waitUntil: 'domcontentloaded' })
  92  |   await expect(page).toHaveURL((url) => url.pathname === `/${persona.audience}/login`)
  93  |   await submitLoginForm(page, persona)
  94  | 
  95  |   await expect
  96  |     .poll(() => {
  97  |       const current = new URL(page.url())
  98  |       return `${current.pathname}${current.search}${current.hash}`
  99  |     })
  100 |     .toBe(`${expectedDestination.pathname}${expectedDestination.search}${expectedDestination.hash}`)
> 101 |   await expect(page.locator(`[data-product="${persona.audience}"]`)).toBeVisible()
      |                                                                      ^ Error: expect(locator).toBeVisible() failed
  102 | }
  103 | 
  104 | /** runtime-isolation.md: settle initial notices before testing unrelated navigation.
  105 |  * Firefox can report an already-active initial worker as an available update.
  106 |  * Exercise its real update button while no user draft exists.
  107 |  */
  108 | export async function settleInitialPwaNotice(page: Page): Promise<void> {
  109 |   await page.evaluate(async () => {
  110 |     await navigator.serviceWorker.ready
  111 |     await new Promise<void>((resolve) =>
  112 |       requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
  113 |     )
  114 |   })
  115 |   const notice = page.getByTestId('pwa-update-state')
  116 |   const update = notice.getByRole('button', { name: 'Обновить сейчас', exact: true })
  117 |   if (await update.isVisible()) {
  118 |     const href = page.url()
  119 |     await Promise.all([page.waitForEvent('load'), update.click()])
  120 |     await expect(page).toHaveURL(href)
  121 |     await expect(page.locator('[data-product="family"]')).toBeVisible()
  122 |   }
  123 |   const close = notice.getByRole('button', { name: /^(Скрыть|Закрыть)$/ })
  124 |   if (await close.isVisible()) await close.click()
  125 | }
  126 | 
```