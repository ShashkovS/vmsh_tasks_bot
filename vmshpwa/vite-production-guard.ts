import { loadEnv, type ConfigEnv } from 'vite'

const forbiddenProductionFlags = ['VITE_ENABLE_MSW', 'VITE_PROTOTYPE'] as const
const explicitDisabledValues = new Set(['', '0', 'false', 'no', 'off'])

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
): void {
  if (command !== 'build') return

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
}
