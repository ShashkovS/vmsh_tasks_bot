import { describe, expect, it } from 'vitest'

import {
  createAuthReturnTo,
  DEFAULT_AUTH_RETURN_TO,
  MAX_AUTH_RETURN_TO_LENGTH,
  createAuthReturnHref,
  sanitizeAuthReturnTo,
  createRouterAuthReturnTo,
  isAuthenticationLoginPath,
} from './intended-route'

describe('safe post-login return route', () => {
  it('keeps an app-relative deep link with search and hash', () => {
    expect(sanitizeAuthReturnTo('/tasks/41n-6?course=math&view=sheet#part-2')).toBe(
      '/tasks/41n-6?course=math&view=sheet#part-2',
    )
    expect(
      createAuthReturnTo('student', {
        pathname: '/student/tasks/41n-6',
        search: '?course=math',
        hash: '#part-2',
      }),
    ).toBe('/tasks/41n-6?course=math#part-2')
  })

  it.each([
    undefined,
    '',
    'tasks',
    ' https://example.invalid',
    'https://example.invalid/tasks',
    '//example.invalid/tasks',
    '/\\example.invalid/tasks',
    '/%5cexample.invalid/tasks',
    '/%2f%2fexample.invalid/tasks',
    '/tasks/%0aheader',
    '/login',
    '/login?returnTo=/tasks',
    '/log%69n',
    '/student/tasks',
    '/%73tudent/tasks',
    '/family/children',
    '/staff/audit',
    `/${'a'.repeat(MAX_AUTH_RETURN_TO_LENGTH)}`,
  ])('falls back for an unsafe value %#', (value) => {
    expect(sanitizeAuthReturnTo(value)).toBe(DEFAULT_AUTH_RETURN_TO)
  })

  it('normalizes dot segments before checking a login loop', () => {
    expect(sanitizeAuthReturnTo('/tasks/../login')).toBe(DEFAULT_AUTH_RETURN_TO)
  })

  it('rejects a browser location outside the expected audience base', () => {
    expect(
      createAuthReturnTo('student', {
        pathname: '/family/children',
        search: '?child=fixture',
      }),
    ).toBe(DEFAULT_AUTH_RETURN_TO)
  })

  it('normalizes an audience-prefixed Staff pathname for route capability matching', () => {
    expect(createRouterAuthReturnTo('staff', { pathname: '/staff/classrooms' })).toBe('/classrooms')
  })

  it('accepts router-local locations without duplicating the hash marker', () => {
    expect(
      createRouterAuthReturnTo('student', {
        pathname: '/tasks/41n-6',
        search: '?course=math',
        hash: '#part-2',
      }),
    ).toBe('/tasks/41n-6?course=math#part-2')
    expect(createAuthReturnHref('student', '/tasks/41n-6#part-2')).toBe(
      '/student/tasks/41n-6#part-2',
    )
  })

  it('recognizes only the local or audience-prefixed login route with trailing slashes', () => {
    for (const audience of ['student', 'family', 'staff'] as const) {
      expect(isAuthenticationLoginPath(audience, '/login')).toBe(true)
      expect(isAuthenticationLoginPath(audience, '/login/')).toBe(true)
      expect(isAuthenticationLoginPath(audience, `/${audience}/login`)).toBe(true)
      expect(isAuthenticationLoginPath(audience, `/${audience}/login/`)).toBe(true)
    }
    expect(isAuthenticationLoginPath('student', '/family/login/')).toBe(false)
    expect(isAuthenticationLoginPath('student', '/tasks/login/')).toBe(false)
  })
})
