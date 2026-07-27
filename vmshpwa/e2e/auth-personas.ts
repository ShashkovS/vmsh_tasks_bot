import credentialFixture from '../../pwa_tests/fixtures/auth-credentials-v1.json' with { type: 'json' }

import { expect, type Page } from './fixtures'

export type AuthAudience = 'student' | 'family' | 'staff'
export type AuthPersonaName = 'student' | 'studentInPerson' | 'family' | 'teacher' | 'admin'

export interface AuthPersona {
  persona: AuthPersonaName
  accountPublicId: string
  audience: AuthAudience
  username: string
  credentialField: 'telegramToken' | 'password'
  credential: string
}

const expectedPersonas: AuthPersonaName[] = [
  'student',
  'studentInPerson',
  'family',
  'teacher',
  'admin',
]

function parseFixture(): Record<AuthPersonaName, AuthPersona> {
  if (
    credentialFixture.fixture !== 'synthetic-auth-credentials-v1' ||
    credentialFixture.fixtureVersion !== 1
  ) {
    throw new Error('Unknown E2E authentication fixture')
  }

  const parsed = new Map<AuthPersonaName, AuthPersona>()
  for (const rawAccount of credentialFixture.accounts) {
    if (
      !expectedPersonas.includes(rawAccount.persona as AuthPersonaName) ||
      !['student', 'family', 'staff'].includes(rawAccount.audience) ||
      !['telegramToken', 'password'].includes(rawAccount.credentialField) ||
      !rawAccount.accountPublicId ||
      !rawAccount.username ||
      !rawAccount.credential.endsWith('-not-a-secret')
    ) {
      throw new Error('Invalid E2E authentication fixture account')
    }
    const account = rawAccount as AuthPersona
    if (
      parsed.has(account.persona) ||
      (account.audience === 'student') !== (account.credentialField === 'telegramToken')
    ) {
      throw new Error('Ambiguous E2E authentication fixture account')
    }
    parsed.set(account.persona, account)
  }
  if (parsed.size !== expectedPersonas.length) {
    throw new Error('Incomplete E2E authentication fixture')
  }
  return Object.fromEntries(parsed) as Record<AuthPersonaName, AuthPersona>
}

/** Test-only personas. No application or production bundle imports this module. */
export const AUTH_PERSONAS = parseFixture()

export function credentialLabel(persona: AuthPersona): string {
  return persona.credentialField === 'telegramToken' ? 'Токен Telegram-бота' : 'Пароль'
}

export async function submitLoginForm(page: Page, persona: AuthPersona): Promise<void> {
  await page.getByLabel('Логин').fill(persona.username)
  await page.getByLabel(credentialLabel(persona), { exact: true }).fill(persona.credential)

  const loginResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/${persona.audience}/api/v1/auth/login`,
  )
  await page.getByRole('button', { name: 'Войти' }).click()
  const response = await loginResponse
  expect(response.status()).toBe(200)
}

/**
 * Complete the real browser login flow through the audience page and aiohttp.
 * See Phase 1's Playwright acceptance matrix in development-plan/05-phase-1-auth.md.
 */
export async function loginThroughUi(
  page: Page,
  persona: AuthPersona,
  intendedRoute = `/${persona.audience}/`,
): Promise<void> {
  const expectedDestination = new URL(intendedRoute, 'http://127.0.0.1:5380')
  await page.goto(intendedRoute)
  await expect(page).toHaveURL((url) => url.pathname === `/${persona.audience}/login`)
  await submitLoginForm(page, persona)

  await expect
    .poll(() => {
      const current = new URL(page.url())
      return `${current.pathname}${current.search}${current.hash}`
    })
    .toBe(`${expectedDestination.pathname}${expectedDestination.search}${expectedDestination.hash}`)
  await expect(page.locator(`[data-product="${persona.audience}"]`)).toBeVisible()
}
