#!/usr/bin/env node
// Bundle size report used by the i18n performance budget
// (vmshpwa/dev/development-plan/24-i18n.md, «Производительность»).
// Usage: node scripts/bundle-report.mjs [--json out.json] [workspaceDir]
// Reads apps/*/dist after `pnpm build`; sizes are brotli quality 11 like the deploy.
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { brotliCompressSync, constants } from 'node:zlib'

const args = process.argv.slice(2)
const jsonIndex = args.indexOf('--json')
const jsonPath = jsonIndex >= 0 ? args[jsonIndex + 1] : undefined
const positional = args.filter((_, index) => index !== jsonIndex && index !== jsonIndex + 1)
const workspace = positional[0] ?? process.cwd()

function brotli(buffer) {
  return brotliCompressSync(buffer, {
    params: { [constants.BROTLI_PARAM_QUALITY]: 11 },
  }).length
}

function kb(bytes) {
  return (bytes / 1024).toFixed(1)
}

function assetsOf(dist) {
  const assets = join(dist, 'assets')
  return existsSync(assets) ? readdirSync(assets).filter((name) => name.endsWith('.js')) : []
}

function reportApp(app) {
  const dist = join(workspace, 'apps', app, 'dist')
  const html = readFileSync(join(dist, 'index.html'), 'utf8')
  const base = /src="(\/[^"]*\/)assets\//.exec(html)?.[1] ?? '/'
  const entry = /<script type="module" crossorigin src="([^"]+)"/.exec(html)?.[1]
  const preloads = [...html.matchAll(/<link rel="modulepreload" crossorigin href="([^"]+)"/g)].map(
    (match) => match[1],
  )
  const toFile = (href) => join(dist, href.slice(base.length))
  const initial = [entry, ...preloads].filter(Boolean)
  const initialRaw = initial.reduce((sum, href) => sum + statSync(toFile(href)).size, 0)
  const initialBrotli = initial.reduce((sum, href) => sum + brotli(readFileSync(toFile(href))), 0)
  const all = assetsOf(dist)
  const totalBrotli = all.reduce(
    (sum, name) => sum + brotli(readFileSync(join(dist, 'assets', name))),
    0,
  )
  const catalogs = Object.fromEntries(
    all
      .filter((name) => /^catalog-(ru|en)-/.test(name))
      .map((name) => [
        name.slice(0, name.indexOf('-', 'catalog-'.length)),
        brotli(readFileSync(join(dist, 'assets', name))),
      ]),
  )
  return {
    app,
    jsChunks: all.length,
    initialChunks: initial.length,
    initialRawBytes: initialRaw,
    initialBrotliBytes: initialBrotli,
    totalBrotliBytes: totalBrotli,
    catalogBrotliBytes: catalogs,
  }
}

const apps = ['student', 'family', 'staff', 'landing'].filter((app) =>
  existsSync(join(workspace, 'apps', app, 'dist', 'index.html')),
)
const rows = apps.map(reportApp)

console.log('| App | Initial JS (br) | Total JS (br) | Chunks | Catalog ru / en (br) |')
console.log('|---|---:|---:|---:|---|')
for (const row of rows) {
  const catalogs = row.catalogBrotliBytes
  const catalogCell =
    'catalog-ru' in catalogs
      ? `${kb(catalogs['catalog-ru'])} / ${kb(catalogs['catalog-en'] ?? 0)} KB`
      : '—'
  console.log(
    `| ${row.app} | ${kb(row.initialBrotliBytes)} KB | ${kb(row.totalBrotliBytes)} KB | ${row.jsChunks} | ${catalogCell} |`,
  )
}
if (jsonPath) writeFileSync(jsonPath, `${JSON.stringify(rows, null, 2)}\n`)
