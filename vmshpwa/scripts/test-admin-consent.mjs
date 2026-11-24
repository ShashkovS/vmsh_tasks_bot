// Browser regression for pwa_tests/integration/test_admin_remote_mcp.py.
import assert from 'node:assert/strict'
import { text } from 'node:stream/consumers'
import { chromium } from 'playwright'

const { url, backend, cookie, callback } = JSON.parse(await text(process.stdin))
const origin = new URL(url).origin
const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  await page.context().addCookies([
    { ...cookie, url: origin },
    { name: 'vmsh-locale', value: 'en', url: origin },
  ])
  // Forward the public test origin to the fixture's ephemeral listener. Preserve
  // browser-generated Origin/Referer and apply the second CSP supplied by nginx.
  await page.route('**/*', async (route) => {
    const req = route.request()
    const target = new URL(req.url())
    if (target.origin !== origin || !target.pathname.endsWith('/authorize')) {
      return route.fulfill({ status: 200, body: 'ok' })
    }
    const response = await route.fetch({
      url: backend + target.pathname + target.search,
      headers: { ...(await req.allHeaders()), host: target.host },
      maxRedirects: 0,
    })
    await route.fulfill({
      response,
      headers: {
        ...response.headers(),
        'content-security-policy':
          response.headers()['content-security-policy'] + ", form-action 'self'",
      },
    })
  })
  for (const decision of ['Deny', 'Allow']) {
    await page.goto(url)
    assert.equal(await page.locator('html').getAttribute('lang'), 'en')
    await page.getByRole('button', { name: decision, exact: true }).click()
    await page.waitForURL(callback + '?**')
    const result = new URL(page.url()).searchParams
    assert.equal(result.get('state'), 'test')
    if (decision === 'Allow') assert.ok(result.get('code'))
    else assert.equal(result.get('error'), 'access_denied')
  }
} finally {
  await browser.close()
}
