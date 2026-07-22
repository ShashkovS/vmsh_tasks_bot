import { chromium } from 'playwright'

const ids = {
  a: 'exploration-art-direction--option-a-listok',
  b: 'exploration-art-direction--option-b-masterskaya',
  c: 'exploration-art-direction--option-c-arhiv',
}

const pairs = [
  ['fg', 'bg'],
  ['fg', 'surface'],
  ['fg', 'paper'],
  ['fg-muted', 'bg'],
  ['fg-muted', 'surface'],
  ['fg-muted', 'paper'],
  ['fg-subtle', 'bg'],
  ['fg-subtle', 'surface'],
  ['primary-fg', 'primary'],
  ['primary', 'bg'],
  ['primary', 'surface'],
  ['success', 'success-surface'],
  ['warning', 'warning-surface'],
  ['danger', 'danger-surface'],
  ['info', 'info-surface'],
  ['level-1', 'level-1-surface'],
  ['level-2', 'level-2-surface'],
  ['level-3', 'level-3-surface'],
  ['level-0', 'level-0-surface'],
  ['success', 'surface'],
  ['warning', 'surface'],
  ['danger', 'surface'],
  ['info', 'surface'],
  ['border-strong', 'surface'],
  ['focus', 'bg'],
  ['focus', 'surface'],
]

const browser = await chromium.launch()
let failures = 0

for (const theme of ['light', 'dark']) {
  for (const [key, id] of Object.entries(ids)) {
    const page = await browser.newPage({ viewport: { width: 900, height: 700 } })
    const story = theme === 'dark' ? `${id}-dark` : id
    await page.goto(
      `http://127.0.0.1:6106/iframe.html?id=${story}&viewMode=story&globals=theme:${theme}`,
      { waitUntil: 'networkidle' },
    )
    const results = await page.evaluate((tokenPairs) => {
      const root = document.querySelector('.ad-root')
      const probe = document.createElement('span')
      root.appendChild(probe)
      // getComputedStyle keeps oklch() as-is, so rasterise to sRGB bytes.
      const canvas = document.createElement('canvas')
      canvas.width = 1
      canvas.height = 1
      const context = canvas.getContext('2d')
      const resolve = (token) => {
        probe.style.color = `var(--ad-${token})`
        context.clearRect(0, 0, 1, 1)
        context.fillStyle = getComputedStyle(probe).color
        context.fillRect(0, 0, 1, 1)
        const [r, g, b] = context.getImageData(0, 0, 1, 1).data
        return [r, g, b]
      }
      const luminance = ([r, g, b]) =>
        [r, g, b]
          .map((channel) => channel / 255)
          .map((channel) =>
            channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
          )
          .reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0)
      const out = tokenPairs.map(([front, back]) => {
        const l1 = luminance(resolve(front))
        const l2 = luminance(resolve(back))
        const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
        return [front, back, Math.round(ratio * 100) / 100]
      })
      probe.remove()
      return out
    }, pairs)

    for (const [front, back, ratio] of results) {
      const isNonText = front === 'border-strong' || front === 'focus'
      const threshold = isNonText ? 3 : 4.5
      const ok = ratio >= threshold
      if (!ok) failures += 1
      if (!ok || process.env.VERBOSE)
        console.log(
          `${ok ? 'ok  ' : 'FAIL'} ${key}/${theme}  ${front} on ${back} = ${ratio} (need ${threshold})`,
        )
    }
    await page.close()
  }
}

console.log(
  failures === 0 ? '\nAll audited pairs pass WCAG 2.2 AA.' : `\n${failures} pair(s) below AA.`,
)
await browser.close()
process.exit(failures === 0 ? 0 : 1)
