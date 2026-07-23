import * as Sentry from '@sentry/react'

export interface FrontendObservabilityOptions {
  audience: 'student' | 'family' | 'staff'
  dsn: string | undefined
  enabled: boolean
  environment: string
  release: string | undefined
}

let initialized = false

export function initFrontendObservability(options: FrontendObservabilityOptions) {
  if (initialized || !options.enabled || !options.dsn) return

  Sentry.init({
    dsn: options.dsn,
    enabled: true,
    environment: options.environment,
    ...(options.release ? { release: options.release } : {}),
    sendDefaultPii: false,
    attachStacktrace: true,
    initialScope: {
      tags: { audience: options.audience },
    },
  })
  initialized = true
}
