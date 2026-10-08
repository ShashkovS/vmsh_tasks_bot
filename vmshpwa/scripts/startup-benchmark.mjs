#!/usr/bin/env node
// Startup benchmark for the i18n performance budget
// (vmshpwa/dev/development-plan/24-i18n.md, «Производительность»).
// Serves apps/<app>/dist with brotli like production nginx, emulates a 4G-like
// network in Chromium and reports median first-contentful-paint for cold
// (new context) and warm (reload) starts. The API is absent on purpose: the
// measured path is bundle + catalog loading up to the runtime startup screen.
// Usage: node scripts/startup-benchmark.mjs [--runs 9] [--workspace dir] app...
import { createServer } from 'node:http'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { extname, join, normalize } from 'node:path'
import { brotliCompressSync, constants } from 'node:zlib'

import { chromium } from 'playwright'

const args = process.argv.slice(2)
function option(name, fallback) {
  const index = args.indexOf(name)
  if (index < 0) return fallback
  const value = args[index + 1]
  args.splice(index, 2)
  return value
}
const runs = Number(option('--runs', '9'))
const workspace = option('--workspace', process.cwd())
const apps = args.length > 0 ? args : ['student', 'family', 'staff']

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.webmanifest': 'application/manifest+json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
}
const compressedCache = new Map()

function serve(app) {
  const dist = join(workspace, 'apps', app, 'dist')
  const base = `/${app}/`
  const server = createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1')
    if (!url.pathname.startsWith(base) || url.pathname.includes('/api/')) {
      response.writeHead(404).end()
      return
    }
    let file = normalize(join(dist, url.pathname.slice(base.length)))
    if (!file.startsWith(dist) || !existsSync(file) || statSync(file).isDirectory()) {
      file = join(dist, 'index.html')
    }
    const type = contentTypes[extname(file)] ?? 'application/octet-stream'
    const immutable = file.includes('/assets/')
    const headers = {
      'content-type': type,
      'cache-control': immutable ? 'public, max-age=31536000, immutable' : 'no-cache',
    }
    let body = readFileSync(file)
    if (/\.(html|js|mjs|css|json|svg)$/.test(file)) {
      let compressed = compressedCache.get(file)
      if (!compressed) {
        compressed = brotliCompressSync(body, {
          params: { [constants.BROTLI_PARAM_QUALITY]: 11 },
        })
        compressedCache.set(file, compressed)
      }
      body = compressed
      headers['content-encoding'] = 'br'
    }
    response.writeHead(200, headers).end(body)
  })
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server))
  })
}

async function firstContentfulPaint(page) {
  await page.waitForFunction(
    () => performance.getEntriesByName('first-contentful-paint').length > 0,
    undefined,
    { timeout: 30_000 },
  )
  return page.evaluate(() => performance.getEntriesByName('first-contentful-paint')[0].startTime)
}

async function emulateNetwork(page) {
  const session = await page.context().newCDPSession(page)
  await session.send('Network.enable')
  await session.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 40,
    downloadThroughput: (12 * 1024 * 1024) / 8,
    uploadThroughput: (4 * 1024 * 1024) / 8,
  })
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)]
}

const browser = await chromium.launch()
const results = []
try {
  for (const app of apps) {
    const server = await serve(app)
    const { port } = server.address()
    const url = `http://127.0.0.1:${port}/${app}/`
    const cold = []
    const warm = []
    for (let run = 0; run < runs; run += 1) {
      const context = await browser.newContext({ serviceWorkers: 'block' })
      const page = await context.newPage()
      await emulateNetwork(page)
      await page.goto(url)
      cold.push(await firstContentfulPaint(page))
      await page.reload()
      warm.push(await firstContentfulPaint(page))
      await context.close()
    }
    server.close()
    results.push({ app, coldFcpMs: median(cold), warmFcpMs: median(warm) })
  }
} finally {
  await browser.close()
}

console.log('| App | Cold FCP (median) | Warm FCP (median) |')
console.log('|---|---:|---:|')
for (const row of results) {
  console.log(`| ${row.app} | ${row.coldFcpMs.toFixed(0)} ms | ${row.warmFcpMs.toFixed(0)} ms |`)
}
