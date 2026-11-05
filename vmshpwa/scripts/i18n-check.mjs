#!/usr/bin/env node
// Frontend i18n gate, run by `make pwa-i18n-check` (see docs/i18n.md):
// 1. catalogs are in sync with the code (`lingui extract --clean` changes nothing);
// 2. every message owned by a translated scope (i18n-scopes.json) has English;
// 3. every app merges the catalog of each `@vmsh/*` package it depends on.
// `--no-extract` skips step 1 for callers that have just extracted.
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join, matchesGlob } from 'node:path'

import { formatter } from '@lingui/format-po'

const workspace = join(import.meta.dirname, '..')
const scopes = JSON.parse(readFileSync(join(workspace, 'i18n-scopes.json'), 'utf8'))
const failures = []

function catalogFiles() {
  const files = []
  for (const group of ['apps', 'packages']) {
    for (const owner of readdirSync(join(workspace, group))) {
      const locales = join(workspace, group, owner, 'src', 'locales')
      if (!existsSync(locales)) continue
      for (const name of readdirSync(locales)) {
        if (name.endsWith('.po')) files.push(join(locales, name))
      }
    }
  }
  return files.sort()
}

// 1. Catalog sync. Extraction rewrites the files in place, so a failure leaves
// the updated catalogs ready to translate and commit.
if (!process.argv.includes('--no-extract')) {
  const before = new Map(catalogFiles().map((file) => [file, readFileSync(file, 'utf8')]))
  execFileSync('pnpm', ['exec', 'lingui', 'extract', '--clean'], {
    cwd: workspace,
    stdio: ['ignore', 'ignore', 'inherit'],
  })
  const after = new Map(catalogFiles().map((file) => [file, readFileSync(file, 'utf8')]))
  const changed = [...new Set([...before.keys(), ...after.keys()])].filter(
    (file) => before.get(file) !== after.get(file),
  )
  if (changed.length > 0) {
    failures.push(
      `Catalogs were out of sync with the code and have been updated; review, translate and commit:\n  ${changed
        .map((file) => file.slice(workspace.length + 1))
        .join('\n  ')}`,
    )
  }
}

// 2. English coverage of translated scopes.
const poFormatter = formatter({ lineNumbers: false })
const untranslated = []
for (const file of catalogFiles().filter((path) => path.endsWith('/en.po'))) {
  const catalog = await poFormatter.parse(readFileSync(file, 'utf8'), {
    locale: 'en',
    sourceLocale: 'ru',
    filename: file,
  })
  for (const entry of Object.values(catalog)) {
    if (entry.obsolete || entry.translation) continue
    const origins = (entry.origin ?? []).map(([path]) => path)
    const scoped = origins.find((origin) =>
      scopes.frontend.some((glob) => matchesGlob(origin, glob)),
    )
    if (scoped) untranslated.push(`${scoped}: ${JSON.stringify(entry.message)}`)
  }
}
if (untranslated.length > 0) {
  failures.push(
    `${untranslated.length} message(s) in translated scopes have no English translation:\n  ${untranslated.join('\n  ')}`,
  )
}

// 3. Every app merges the catalogs of all `@vmsh/*` packages it depends on.
function workspacePackage(name) {
  const directory = join(workspace, 'packages', name.slice('@vmsh/'.length))
  return existsSync(join(directory, 'package.json')) ? directory : null
}

function catalogPackages(manifestDirectory, seen = new Set()) {
  const manifest = JSON.parse(readFileSync(join(manifestDirectory, 'package.json'), 'utf8'))
  for (const name of Object.keys(manifest.dependencies ?? {})) {
    if (!name.startsWith('@vmsh/') || seen.has(name)) continue
    const directory = workspacePackage(name)
    if (!directory) continue
    seen.add(name)
    catalogPackages(directory, seen)
  }
  return seen
}

for (const app of readdirSync(join(workspace, 'apps'))) {
  const appDirectory = join(workspace, 'apps', app)
  if (!existsSync(join(appDirectory, 'package.json'))) continue
  const required = [...catalogPackages(appDirectory)]
    .filter((name) => existsSync(join(workspacePackage(name), 'src', 'locales')))
    .sort()
  for (const locale of ['ru', 'en']) {
    const module = join(appDirectory, 'src', 'i18n', `catalog-${locale}.ts`)
    if (!existsSync(module)) {
      failures.push(`apps/${app} has no src/i18n/catalog-${locale}.ts`)
      continue
    }
    const source = readFileSync(module, 'utf8')
    const merged = new Set(
      [...source.matchAll(/from '(@vmsh\/[^/']+)\/locales\/(\w+)\.po'/g)]
        .filter((match) => match[2] === locale)
        .map((match) => match[1]),
    )
    const missing = required.filter((name) => !merged.has(name))
    if (missing.length > 0) {
      failures.push(
        `apps/${app}/src/i18n/catalog-${locale}.ts does not merge: ${missing.join(', ')}`,
      )
    }
    if (!source.includes(`from '../locales/${locale}.po'`)) {
      failures.push(`apps/${app}/src/i18n/catalog-${locale}.ts does not merge its own catalog`)
    }
  }
}

if (failures.length > 0) {
  console.error(failures.join('\n\n'))
  process.exit(1)
}
console.log('i18n catalogs: in sync, translated scopes covered, app catalogs complete')
