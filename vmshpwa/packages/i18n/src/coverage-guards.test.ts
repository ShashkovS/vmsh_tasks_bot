/// <reference types="node" />
// @vitest-environment node
import { spawnSync } from 'node:child_process'
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { afterEach, expect, it } from 'vitest'

const workspace = resolve(import.meta.dirname, '../../..')
const temporary: string[] = []
afterEach(() =>
  temporary.splice(0).forEach((path) => rmSync(path, { recursive: true, force: true })),
)

function fixture(translation: string, mergeShared: boolean) {
  const root = mkdtempSync(join(tmpdir(), 'vmsh-i18n-guard-'))
  temporary.push(root)
  function write(path: string, content: string) {
    const target = join(root, path)
    mkdirSync(resolve(target, '..'), { recursive: true })
    writeFileSync(target, content)
  }
  write('scripts/i18n-check.mjs', '')
  copyFileSync(join(workspace, 'scripts/i18n-check.mjs'), join(root, 'scripts/i18n-check.mjs'))
  symlinkSync(join(workspace, 'node_modules'), join(root, 'node_modules'), 'dir')
  write('i18n-scopes.json', JSON.stringify({ frontend: ['apps/*/src/**/*.tsx'] }))
  write('packages/ui/package.json', '{}')
  write('packages/ui/src/locales/en.po', '')
  write('apps/demo/package.json', JSON.stringify({ dependencies: { '@vmsh/ui': 'workspace:*' } }))
  write(
    'apps/demo/src/locales/en.po',
    `#: apps/demo/src/page.tsx\nmsgid "Проверка"\nmsgstr ${JSON.stringify(translation)}\n`,
  )
  for (const locale of ['ru', 'en']) {
    write(
      `apps/demo/src/i18n/catalog-${locale}.ts`,
      `import own from '../locales/${locale}.po'\n` +
        (mergeShared ? `import shared from '@vmsh/ui/locales/${locale}.po'\n` : ''),
    )
  }
  return spawnSync(process.execPath, [join(root, 'scripts/i18n-check.mjs'), '--no-extract'], {
    encoding: 'utf8',
  })
}

// P8: actual checker, isolated fixture; no repository catalogs are mutated.
it('rejects missing English but accepts a complete merged catalog', () => {
  expect(fixture('Review', true).status).toBe(0)
  const missing = fixture('', true)
  expect(missing.status).toBe(1)
  expect(missing.stderr).toContain('have no English translation')
})

it('rejects an unmerged transitive catalog dependency', () => {
  const result = fixture('Review', false)
  expect(result.status).toBe(1)
  expect(result.stderr).toContain('does not merge: @vmsh/ui')
})

it('rejects raw production UI copy through the real ESLint configuration', () => {
  const result = spawnSync(
    process.execPath,
    [
      join(workspace, 'node_modules/eslint/bin/eslint.js'),
      '--stdin',
      '--stdin-filename',
      'apps/landing/src/landing-page.tsx',
    ],
    {
      cwd: workspace,
      input: 'export function Page() { return <p>Новая строка</p> }',
      encoding: 'utf8',
    },
  )
  expect(result.status).toBe(1)
  expect(result.stdout).toContain('lingui/no-unlocalized-strings')
}, 30_000)
