import { z } from 'zod'
import { brandingSelectionSchema } from '../packages/contracts/src/branding'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// Real isolated backend; restore the shared fixture's profile after every run.
// See docs/branding.md. No production mock authentication or routes.
test('admin selects TLF; new devices use English and branded install assets', async ({
  page,
  browser,
}, info) => {
  test.setTimeout(90_000)
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/branding')
  try {
    await page.getByRole('radio', { name: 'TLF Prep Clubs', exact: true }).check()
    await page.getByRole('button', { name: 'Применить', exact: true }).click()
    await expect(page.locator('html')).toHaveAttribute('data-brand', 'tlf-prep-clubs')
    await expect(page.getByRole('radio', { name: 'TLF Prep Clubs', exact: true })).toBeChecked()
    await page.screenshot({ path: info.outputPath('branding-admin.png'), fullPage: true })

    const fresh = await browser.newContext({
      baseURL: 'http://127.0.0.1:5380',
      viewport: { width: 390, height: 844 },
    })
    try {
      const visitor = await fresh.newPage()
      await visitor.goto('/')
      await expect(visitor.locator('html')).toHaveAttribute('lang', 'en')
      await expect(visitor).toHaveTitle(/TLF Prep Clubs/)
      await expect(visitor.getByRole('link', { name: 'Open account' }).first()).toBeVisible()
      await visitor.screenshot({
        path: info.outputPath('branding-landing-mobile.png'),
        fullPage: true,
      })
      for (const audience of ['student', 'family', 'staff']) {
        await visitor.goto(`/${audience}/login`)
        await expect(visitor.locator('html')).toHaveAttribute('lang', 'en')
        await expect(visitor.getByText('TLF Prep Clubs', { exact: true }).first()).toBeVisible()
        await expect(visitor.getByRole('link', { name: 'info@leaders.tech' })).toBeVisible()
        expect(
          await visitor.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        ).toBe(true)
        await visitor.screenshot({
          path: info.outputPath(`branding-${audience}-mobile.png`),
          fullPage: true,
        })
      }
      for (const audience of ['student', 'family']) {
        const response = await fresh.request.get(`/${audience}/manifest.webmanifest`)
        expect(response.ok()).toBe(true)
        const manifest = z
          .object({
            name: z.string(),
            lang: z.string(),
            id: z.string(),
            icons: z.array(z.object({ src: z.string() })),
          })
          .parse(await response.json())
        expect(manifest.name).toContain('TLF Prep Clubs')
        expect(manifest.lang).toBe('en')
        expect(manifest.id).toBe(`/${audience}/`)
        for (const icon of manifest.icons)
          expect((await fresh.request.get(icon.src)).ok()).toBe(true)
      }
      await fresh.addCookies([{ name: 'vmsh-locale', value: 'ru', url: 'http://127.0.0.1:5380' }])
      await visitor.reload()
      await expect(visitor.locator('html')).toHaveAttribute('lang', 'ru')
    } finally {
      await fresh.close()
    }
  } finally {
    const response = await page.request.get('/staff/api/v1/branding')
    const current = brandingSelectionSchema.parse(await response.json())
    const restored = await page.request.put('/staff/api/v1/branding', {
      headers: { Origin: 'http://127.0.0.1:5380' },
      data: { profileId: 'vmsh', version: current.version },
    })
    expect(restored.ok()).toBe(true)
  }
})
