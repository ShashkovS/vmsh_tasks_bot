import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { assertSafeProductionBuild } from '../../../vite-production-guard'

const temporaryDirectories: string[] = []

function environmentDirectory(contents = ''): string {
  const directory = mkdtempSync(join(tmpdir(), 'vmsh-vite-production-guard-'))
  temporaryDirectories.push(directory)
  if (contents) writeFileSync(join(directory, '.env.production'), contents, 'utf8')
  return directory
}

afterEach(() => {
  vi.unstubAllEnvs()
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { force: true, recursive: true })
  }
})

describe('production Vite guard', () => {
  it.each(['VITE_ENABLE_MSW', 'VITE_PROTOTYPE'] as const)(
    'rejects %s loaded from .env.production before build output is touched',
    (flag) => {
      vi.stubEnv(flag, undefined)
      const envDir = environmentDirectory(`${flag}=true\n`)

      expect(() =>
        assertSafeProductionBuild({ command: 'build', mode: 'production' }, envDir),
      ).toThrow(flag)
    },
  )

  it('honours an explicit disabled process value over a mode file', () => {
    vi.stubEnv('VITE_PROTOTYPE', 'false')
    const envDir = environmentDirectory('VITE_PROTOTYPE=true\n')

    expect(() =>
      assertSafeProductionBuild({ command: 'build', mode: 'production' }, envDir),
    ).not.toThrow()
  })

  it('allows prototype flags while serving development', () => {
    const envDir = environmentDirectory('VITE_PROTOTYPE=true\n')

    expect(() =>
      assertSafeProductionBuild({ command: 'serve', mode: 'development' }, envDir),
    ).not.toThrow()
  })

  it('rejects ambiguous enabled values instead of silently building', () => {
    const envDir = environmentDirectory('VITE_ENABLE_MSW=unexpected\n')

    expect(() =>
      assertSafeProductionBuild({ command: 'build', mode: 'production' }, envDir),
    ).toThrow('VITE_ENABLE_MSW')
  })
})
