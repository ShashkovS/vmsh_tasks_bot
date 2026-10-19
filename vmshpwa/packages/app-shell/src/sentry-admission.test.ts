import type { Event } from '@sentry/react'
import { expect, it, vi } from 'vitest'
import { createSentryAdmission } from './sentry-admission'

const event: Event = {
  fingerprint: ['pwa-handled-v1', 'test.submit', 'api', '500', 'unexpected'],
  user: { id: 'private-account' },
  extra: { answer: 'private-answer', telemetry: { lane: 'error' } },
}

function requestPayload(options: RequestInit | undefined): unknown {
  if (typeof options?.body !== 'string') throw new Error('Expected a JSON string body')
  return JSON.parse(options.body)
}

it('reserves through the audience endpoint using only a lane and bounded hash', async () => {
  const send = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ allowed: true }))
  const admit = createSentryAdmission('student', { fetch: send })
  expect(await admit(event)).toBe(true)
  const [path, options] = send.mock.calls[0]!
  expect(path).toBe('/student/api/v1/observability/sentry-admission')
  expect(options).toMatchObject({ credentials: 'omit', mode: 'same-origin', redirect: 'error' })
  expect(requestPayload(options)).toEqual({
    lane: 'error',
    signature: expect.stringMatching(/^[0-9a-f]{8}$/),
  })
  expect(JSON.stringify(send.mock.calls)).not.toContain('private')
})

it('keeps diagnostics in their own reserve across every audience', async () => {
  for (const audience of ['family', 'staff'] as const) {
    const send = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ allowed: true }))
    expect(
      await createSentryAdmission(audience, { fetch: send })({
        ...event,
        extra: { telemetry: { lane: 'query' } },
      }),
    ).toBe(true)
    expect(requestPayload(send.mock.calls[0]?.[1])).toMatchObject({ lane: 'query' })
    expect(send.mock.calls[0]?.[0]).toBe(`/${audience}/api/v1/observability/sentry-admission`)
  }
})

it('fails closed on refusal, missing endpoint, malformed response, offline and timeout without retry', async () => {
  const send = vi.fn<typeof fetch>()
  const admit = createSentryAdmission('student', { fetch: send })
  for (const response of [
    Response.json({ allowed: false }),
    Response.json({ allowed: 'true' }),
    Response.json(null),
    new Response('not JSON'),
    new Response('not found', { status: 404 }),
    new Response('busy', { status: 503 }),
  ]) {
    send.mockResolvedValueOnce(response)
    expect(await admit(event)).toBe(false)
  }
  send.mockRejectedValueOnce(new TypeError('offline'))
  expect(await admit(event)).toBe(false)
  send.mockRejectedValueOnce(new DOMException('Timed out', 'TimeoutError'))
  expect(await admit(event)).toBe(false)
  expect(send).toHaveBeenCalledTimes(8)
})
