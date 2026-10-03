/*
 * Contrast audit for the real semantic tokens (packages/ui globals.css).
 * Loads a Storybook story so globals.css is applied, reads :root (light) and
 * .dark (dark) custom properties, rasterises each oklch() to sRGB and checks
 * WCAG 2.2 AA: 4.5:1 for text, 3:1 for borders / focus / non-text.
 *
 * Run with Storybook up on 6106:
 *   node dev/design-system/tokens-contrast-audit.mjs
 */
import { chromium } from 'playwright'

// [front, back, kind] — kind 'text' → 4.5, 'ui' → 3.0
const pairs = [
  ['foreground', 'background', 'text'],
  ['foreground', 'surface', 'text'],
  ['foreground', 'surface-subtle', 'text'],
  ['foreground', 'surface-sunken', 'text'],
  ['foreground', 'paper', 'text'],
  ['foreground', 'muted', 'text'],
  ['muted-foreground', 'background', 'text'],
  ['muted-foreground', 'surface', 'text'],
  ['muted-foreground', 'muted', 'text'],
  ['foreground-subtle', 'background', 'text'],
  ['foreground-subtle', 'surface', 'text'],
  ['placeholder', 'surface', 'text'],
  ['placeholder', 'background', 'text'],
  ['primary', 'background', 'text'],
  ['primary', 'surface', 'text'],
  ['primary-foreground', 'primary', 'text'],
  ['secondary-foreground', 'secondary', 'text'],
  ['accent-foreground', 'accent', 'text'],
  ['destructive-foreground', 'destructive', 'text'],
  ['link', 'background', 'text'],
  ['link', 'surface', 'text'],
  ['unread-foreground', 'unread', 'text'],
  ['provenance-ai', 'provenance-ai-surface', 'text'],
  ['provenance-ai', 'surface', 'text'],
  // status
  ...['success', 'warning', 'danger', 'info'].flatMap((s) => [
    [`status-${s}-foreground`, `status-${s}`, 'text'],
    [`status-${s}`, `status-${s}-surface`, 'text'],
    [`status-${s}`, 'surface', 'text'],
    [`status-${s}-border`, 'surface', 'ui'],
  ]),
  // levels
  ...['1', '2', '3', '4', '0'].flatMap((n) => [
    [`level-${n}`, `level-${n}-surface`, 'text'],
    [`level-${n}`, 'surface', 'text'],
    [`level-${n}-border`, 'surface', 'ui'],
  ]),
  // verdict
  ...['negative', 'partial-low', 'partial-mid', 'partial-high', 'positive', 'none'].flatMap((v) => [
    [`verdict-${v}`, `verdict-${v}-surface`, 'text'],
    [`verdict-${v}`, 'surface', 'text'],
  ]),
  // non-text
  ['border-strong', 'surface', 'ui'],
  ['border-interactive', 'surface', 'ui'],
  ['focus-ring', 'background', 'ui'],
  ['focus-ring', 'surface', 'ui'],
  ['provenance-ai-border', 'surface', 'ui'],
]

const browser = await chromium.launch()
let failures = 0

for (const theme of ['light', 'dark']) {
  const page = await browser.newPage({ viewport: { width: 800, height: 600 } })
  await page.goto(`http://127.0.0.1:6106/iframe.html?id=foundations-tokens--light&viewMode=story`, {
    waitUntil: 'networkidle',
  })
  // Apply the theme directly so we read the real cascade, not URL-global timing.
  await page.evaluate((mode) => {
    document.documentElement.classList.toggle('dark', mode === 'dark')
    document.documentElement.style.colorScheme = mode
  }, theme)
  const results = await page.evaluate((tokenPairs) => {
    const probe = document.createElement('span')
    document.body.appendChild(probe)
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 1
    const ctx = canvas.getContext('2d')
    const resolve = (token) => {
      probe.style.color = `var(--${token})`
      ctx.clearRect(0, 0, 1, 1)
      ctx.fillStyle = getComputedStyle(probe).color
      ctx.fillRect(0, 0, 1, 1)
      return [...ctx.getImageData(0, 0, 1, 1).data.slice(0, 3)]
    }
    const lum = (rgb) =>
      rgb
        .map((c) => c / 255)
        .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
        .reduce((s, c, i) => s + c * [0.2126, 0.7152, 0.0722][i], 0)
    const out = tokenPairs.map(([front, back, kind]) => {
      const l1 = lum(resolve(front))
      const l2 = lum(resolve(back))
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
      return [front, back, kind, Math.round(ratio * 100) / 100]
    })
    probe.remove()
    return out
  }, pairs)

  for (const [front, back, kind, ratio] of results) {
    const threshold = kind === 'ui' ? 3 : 4.5
    const ok = ratio >= threshold
    if (!ok) failures += 1
    if (!ok || process.env.VERBOSE)
      console.log(
        `${ok ? 'ok  ' : 'FAIL'} ${theme}  ${front} on ${back} = ${ratio} (need ${threshold})`,
      )
  }
  await page.close()
}

console.log(
  failures === 0
    ? '\nAll audited token pairs pass WCAG 2.2 AA.'
    : `\n${failures} pair(s) below AA.`,
)
await browser.close()
process.exit(failures === 0 ? 0 : 1)
