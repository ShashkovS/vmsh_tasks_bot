import { loadEnv, type ConfigEnv, type Plugin } from 'vite'

const forbiddenProductionFlags = ['VITE_ENABLE_MSW', 'VITE_PROTOTYPE'] as const
const explicitDisabledValues = new Set(['', '0', 'false', 'no', 'off'])
const releaseIdPattern = /^[a-z0-9][a-z0-9._-]{0,63}$/

export interface FrontendBuildProvenance {
  application: 'student' | 'family' | 'staff'
  msw: false
  profile: 'production' | 'verification'
  prototype: false
  publicMediaOrigin: string | null
  releaseId: string | null
  schemaVersion: 1
  sentryConfigured: boolean
  sentryOrigin: string | null
}

type SharedBuildProvenance = Omit<FrontendBuildProvenance, 'application'>

function exactHttpsOrigin(value: string, name: string): string {
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error(`${name} must be one exact HTTPS origin`)
  }
  if (
    parsed.protocol !== 'https:' ||
    parsed.username !== '' ||
    parsed.password !== '' ||
    parsed.pathname !== '/' ||
    parsed.search !== '' ||
    parsed.hash !== '' ||
    value !== parsed.origin
  ) {
    throw new Error(`${name} must be one exact HTTPS origin`)
  }
  return parsed.origin
}

function sentryOrigin(value: string): string {
  let parsed: URL
  try {
    parsed = new URL(value)
  } catch {
    throw new Error('VITE_SENTRY_DSN must be a complete HTTPS Sentry DSN')
  }
  if (
    parsed.protocol !== 'https:' ||
    parsed.username === '' ||
    parsed.password !== '' ||
    parsed.pathname === '/' ||
    parsed.search !== '' ||
    parsed.hash !== ''
  ) {
    throw new Error('VITE_SENTRY_DSN must be a complete HTTPS Sentry DSN')
  }
  // A Sentry DSN is public browser configuration, but release metadata needs
  // only the CSP origin. Never duplicate its project key/path into reports.
  return parsed.origin
}

function resolveBuildProvenance(
  { command, mode }: Pick<ConfigEnv, 'command' | 'mode'>,
  envDir: string,
): SharedBuildProvenance {
  const environment = loadEnv(mode, envDir, ['VITE_', 'VMSH_FRONTEND_BUILD_PROFILE'])
  const profileValue = environment.VMSH_FRONTEND_BUILD_PROFILE?.trim() ?? ''
  if (profileValue !== '' && profileValue !== 'verification' && profileValue !== 'production') {
    throw new Error('VMSH_FRONTEND_BUILD_PROFILE must be verification or production')
  }
  const profile = profileValue === 'production' ? 'production' : 'verification'

  if (command !== 'build' || profile === 'verification') {
    return {
      schemaVersion: 1,
      profile: 'verification',
      releaseId: null,
      publicMediaOrigin: null,
      sentryConfigured: false,
      sentryOrigin: null,
      msw: false,
      prototype: false,
    }
  }

  const releaseId = environment.VITE_SENTRY_RELEASE?.trim() ?? ''
  if (!releaseIdPattern.test(releaseId)) {
    throw new Error('VITE_SENTRY_RELEASE must be the exact lowercase production release ID')
  }
  const publicMediaOrigin = exactHttpsOrigin(
    environment.VITE_PUBLIC_MEDIA_ORIGIN?.trim() ?? '',
    'VITE_PUBLIC_MEDIA_ORIGIN',
  )
  const dsn = environment.VITE_SENTRY_DSN?.trim() ?? ''
  return {
    schemaVersion: 1,
    profile,
    releaseId,
    publicMediaOrigin,
    sentryConfigured: true,
    sentryOrigin: sentryOrigin(dsn),
    msw: false,
    prototype: false,
  }
}

/**
 * Reject test-only frontend modes before Vite can empty the build directory.
 *
 * Vite evaluates its config before it loads mode-specific `.env` files into
 * `import.meta.env`, so checking `process.env` alone misses `.env.production`
 * and `.env.production.local`. `loadEnv` is the documented config-time
 * boundary and preserves process-environment precedence. See Phase 0 in
 * `dev/development-plan/04-phase-0-baseline.md` and the build-guard tests.
 */
export function assertSafeProductionBuild(
  { command, mode }: Pick<ConfigEnv, 'command' | 'mode'>,
  envDir: string,
): SharedBuildProvenance {
  if (command !== 'build') return resolveBuildProvenance({ command, mode }, envDir)

  const environment = loadEnv(mode, envDir, 'VITE_')
  const unsafeFlags = forbiddenProductionFlags.filter((name) => {
    const value = environment[name]
    return value !== undefined && !explicitDisabledValues.has(value.trim().toLowerCase())
  })
  if (unsafeFlags.length > 0) {
    throw new Error(
      `MSW and prototype mode must never be enabled in a production build: ${unsafeFlags.join(', ')}`,
    )
  }
  return resolveBuildProvenance({ command, mode }, envDir)
}

export function buildProvenancePlugin(
  application: FrontendBuildProvenance['application'],
  provenance: SharedBuildProvenance,
): Plugin {
  return {
    name: `vmsh-build-provenance-${application}`,
    apply: 'build',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'build-provenance.json',
        source: `${JSON.stringify({ ...provenance, application }, null, 2)}\n`,
      })
    },
  }
}
