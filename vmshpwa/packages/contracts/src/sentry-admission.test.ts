import { expect, it } from 'vitest'
import { sentryAdmissionRequestSchema, sentryAdmissionResponseSchema } from './sentry-admission'

it('allows only a bounded lane/hash request and a boolean admission response', () => {
  expect(sentryAdmissionRequestSchema.parse({ lane: 'error', signature: 'deadbeef' })).toEqual({
    lane: 'error',
    signature: 'deadbeef',
  })
  for (const value of [
    { lane: 'query', signature: 'private answer' },
    { lane: 'recovery', signature: 'deadbeef' },
    { lane: 'error', signature: 'deadbeef', accountId: 'private' },
  ])
    expect(sentryAdmissionRequestSchema.safeParse(value).success).toBe(false)
  expect(sentryAdmissionResponseSchema.parse({ allowed: false })).toEqual({ allowed: false })
  expect(sentryAdmissionResponseSchema.safeParse({ allowed: 'true' }).success).toBe(false)
})
