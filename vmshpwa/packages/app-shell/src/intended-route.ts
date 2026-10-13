import { runtimeBoundaryByAudience, type Audience } from '@vmsh/contracts'

export const DEFAULT_AUTH_RETURN_TO = '/' as const
export const MAX_AUTH_RETURN_TO_LENGTH = 2048

const SAFE_PARSE_ORIGIN = 'https://vmsh-return.invalid'
const audienceRootPattern = /^\/(?:student|family|staff)(?:\/|$)/
const loginPathPattern = /^\/login\/?$/

function hasUnsafeDecodedCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0
    return character === '\\' || codePoint <= 0x1f || codePoint === 0x7f
  })
}

/**
 * Validate an app-relative post-login destination. It never accepts an origin
 * or audience base, so a Student login cannot become an open redirect or jump
 * into another cabinet. See Phase 1's intended-route acceptance criterion.
 */
export function sanitizeAuthReturnTo(value: unknown): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > MAX_AUTH_RETURN_TO_LENGTH) {
    return DEFAULT_AUTH_RETURN_TO
  }
  if (value !== value.trim() || !value.startsWith('/') || value.startsWith('//')) {
    return DEFAULT_AUTH_RETURN_TO
  }

  let decoded: string
  try {
    decoded = decodeURIComponent(value)
  } catch {
    return DEFAULT_AUTH_RETURN_TO
  }
  if (decoded.startsWith('//') || hasUnsafeDecodedCharacter(decoded)) {
    return DEFAULT_AUTH_RETURN_TO
  }

  let parsed: URL
  try {
    parsed = new URL(value, SAFE_PARSE_ORIGIN)
  } catch {
    return DEFAULT_AUTH_RETURN_TO
  }
  if (parsed.origin !== SAFE_PARSE_ORIGIN) return DEFAULT_AUTH_RETURN_TO
  const decodedPathname = decodeURIComponent(parsed.pathname)
  if (audienceRootPattern.test(decodedPathname) || loginPathPattern.test(decodedPathname)) {
    return DEFAULT_AUTH_RETURN_TO
  }

  const result = `${parsed.pathname}${parsed.search}${parsed.hash}`
  return result.length <= MAX_AUTH_RETURN_TO_LENGTH ? result : DEFAULT_AUTH_RETURN_TO
}

export interface BrowserRouteLocation {
  pathname: string
  search?: string
  hash?: string
}

/** Convert the browser's audience-prefixed location into a safe route-local value. */
export function createAuthReturnTo(audience: Audience, location: BrowserRouteLocation): string {
  const appBase = runtimeBoundaryByAudience[audience].appBase
  if (location.pathname !== appBase && !location.pathname.startsWith(`${appBase}/`)) {
    return DEFAULT_AUTH_RETURN_TO
  }
  const localPath = location.pathname.slice(appBase.length) || '/'
  return sanitizeAuthReturnTo(`${localPath}${location.search ?? ''}${location.hash ?? ''}`)
}

/** Accept both browser-prefixed and router-local locations. */
export function createRouterAuthReturnTo(
  audience: Audience,
  location: BrowserRouteLocation,
): string {
  const appBase = runtimeBoundaryByAudience[audience].appBase
  if (location.pathname === appBase || location.pathname.startsWith(`${appBase}/`)) {
    return createAuthReturnTo(audience, location)
  }
  return sanitizeAuthReturnTo(`${location.pathname}${location.search ?? ''}${location.hash ?? ''}`)
}

export function createAuthReturnHref(audience: Audience, returnTo: unknown): string {
  return `${runtimeBoundaryByAudience[audience].appBase}${sanitizeAuthReturnTo(returnTo)}`
}

export function isAuthenticationLoginPath(audience: Audience, pathname: string): boolean {
  const normalizedPathname = pathname.length > 1 ? pathname.replace(/\/+$/, '') : pathname
  return (
    normalizedPathname === '/login' ||
    normalizedPathname === `${runtimeBoundaryByAudience[audience].appBase}/login`
  )
}
