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

  it('marks an ordinary credential-free build as verification-only', () => {
    const provenance = assertSafeProductionBuild(
      { command: 'build', mode: 'production' },
      environmentDirectory(),
    )

    expect(provenance).toEqual({
      schemaVersion: 1,
      profile: 'verification',
      releaseId: null,
      publicMediaOrigin: null,
      sentryConfigured: false,
      sentryOrigin: null,
      msw: false,
      prototype: false,
    })
  })

  it('records only non-secret origins for an explicit production build', () => {
    const provenance = assertSafeProductionBuild(
      { command: 'build', mode: 'production' },
      environmentDirectory(
        [
          'VMSH_FRONTEND_BUILD_PROFILE=production',
          'VITE_SENTRY_RELEASE=pilot-2026.08.09',
          'VITE_PUBLIC_MEDIA_ORIGIN=https://media.vmsh.example',
          'VITE_SENTRY_DSN=https://public-key@errors.example/179',
          '',
        ].join('\n'),
      ),
    )

    expect(provenance).toEqual({
      schemaVersion: 1,
      profile: 'production',
      releaseId: 'pilot-2026.08.09',
      publicMediaOrigin: 'https://media.vmsh.example',
      sentryConfigured: true,
      sentryOrigin: 'https://errors.example',
      msw: false,
      prototype: false,
    })
  })

  it.each([
    ['missing release', 'VITE_SENTRY_RELEASE='],
    ['media path', 'VITE_PUBLIC_MEDIA_ORIGIN=https://media.vmsh.example/path'],
    ['incomplete Sentry DSN', 'VITE_SENTRY_DSN=https://errors.example/179'],
  ])('rejects incomplete production provenance: %s', (_label, replacement) => {
    const values = new Map([
      ['VITE_SENTRY_RELEASE', 'VITE_SENTRY_RELEASE=pilot-2026.08.09'],
      ['VITE_PUBLIC_MEDIA_ORIGIN', 'VITE_PUBLIC_MEDIA_ORIGIN=https://media.vmsh.example'],
      ['VITE_SENTRY_DSN', 'VITE_SENTRY_DSN=https://public-key@errors.example/179'],
    ])
    const name = replacement.slice(0, replacement.indexOf('='))
    values.set(name, replacement)
    const envDir = environmentDirectory(
      ['VMSH_FRONTEND_BUILD_PROFILE=production', ...values.values(), ''].join('\n'),
    )

    expect(() =>
      assertSafeProductionBuild({ command: 'build', mode: 'production' }, envDir),
    ).toThrow()
  })
})
