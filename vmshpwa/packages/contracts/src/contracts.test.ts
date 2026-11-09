import { describe, expect, it, vi } from 'vitest'

import conflictErrorFixture from '../fixtures/errors/conflict.v1.json'
import forbiddenErrorFixture from '../fixtures/errors/forbidden.v1.json'
import unauthenticatedErrorFixture from '../fixtures/errors/unauthenticated.v1.json'
import familyRuntimeFixture from '../fixtures/runtime/family.v1.json'
import staffRuntimeFixture from '../fixtures/runtime/staff.v1.json'
import studentRuntimeFixture from '../fixtures/runtime/student.v1.json'
import invalidJsonRealtimeFixture from '../fixtures/realtime/invalid-json.v1.json'

import type { ApiResponseError } from './index'
import {
  BROWSER_STORAGE_NAMESPACE_VERSION,
  apiErrorContractFixtureSchema,
  browserStorageNamespaceSchema,
  createBrowserStorageNamespace,
  fetchRuntime,
  lessonDeadlinePolicy,
  offlineMutationSchema,
  parseRuntimeConfigForAudience,
  queryKeys,
  realtimeEventSchema,
  runtimeContractFixtureSchema,
  runtimeConfigSchema,
  runtimeInstanceSchema,
  sessionPolicy,
  submissionImagePolicy,
} from './index'

const runtimeFixtures: unknown[] = [
  studentRuntimeFixture,
  familyRuntimeFixture,
  staffRuntimeFixture,
]

const errorFixtures: unknown[] = [
  unauthenticatedErrorFixture,
  forbiddenErrorFixture,
  conflictErrorFixture,
]

describe('runtime contracts', () => {
  it('accepts an isolated student runtime', () => {
    expect(
      runtimeConfigSchema.parse({
        contractVersion: 1,
        audience: 'student',
        appBase: '/student',
        apiBase: '/student/api/v1',
        websocketPath: '/student/ws',
        instance: 'agent',
        serverTime: '2026-07-22T12:00:00Z',
        requestId: 'req-1',
        features: { telegram: false, google: false, nats: false, prototype: true },
      }).instance,
    ).toBe('agent')
  })

  it.each([
    ['audience', 'family'],
    ['appBase', '/family'],
    ['apiBase', '/family/api/v1'],
    ['websocketPath', '/family/ws'],
  ] as const)('fails closed when student runtime %s crosses an audience boundary', (key, value) => {
    expect(() =>
      parseRuntimeConfigForAudience('student', {
        ...studentRuntimeFixture.response,
        [key]: value,
      }),
    ).toThrow()
  })

  it.each([' Agent', 'agent ', 'AGENT', 'agent:other', 'agent/other', '.agent'])(
    'rejects unsafe or non-canonical runtime instance %s',
    (instance) => {
      expect(() => runtimeInstanceSchema.parse(instance)).toThrow()
    },
  )

  it('derives collision-free browser namespaces from audience and server instance', () => {
    const prefix = `vmsh-179:v${BROWSER_STORAGE_NAMESPACE_VERSION}`
    const namespaces = runtimeFixtures.map((fixture) => {
      const parsed = runtimeContractFixtureSchema.parse(fixture)
      return createBrowserStorageNamespace(parsed.response)
    })

    expect(new Set(namespaces).size).toBe(3)
    expect(namespaces).toEqual([
      `${prefix}:student:agent`,
      `${prefix}:family:agent`,
      `${prefix}:staff:agent`,
    ])
    expect(createBrowserStorageNamespace({ audience: 'student', instance: 'human' })).not.toBe(
      createBrowserStorageNamespace({ audience: 'student', instance: 'agent' }),
    )
    for (const namespace of namespaces) {
      expect(browserStorageNamespaceSchema.parse(namespace)).toBe(namespace)
    }
    expect(() =>
      browserStorageNamespaceSchema.parse(
        `vmsh-179:v${BROWSER_STORAGE_NAMESPACE_VERSION + 1}:student:agent`,
      ),
    ).toThrow()
  })

  it('keeps all versioned runtime fixtures in parity with their strict contracts', () => {
    for (const fixture of runtimeFixtures) {
      expect(runtimeContractFixtureSchema.parse(fixture)).toEqual(fixture)
    }
  })

  it('accepts additive rolling-deploy fields but rejects an unsupported contract version', () => {
    expect(
      parseRuntimeConfigForAudience('student', {
        ...studentRuntimeFixture.response,
        futureServerField: 'ignored by v1',
        features: {
          ...studentRuntimeFixture.response.features,
          futureFeature: true,
        },
      }),
    ).toEqual(studentRuntimeFixture.response)
    expect(() =>
      parseRuntimeConfigForAudience('student', {
        ...studentRuntimeFixture.response,
        contractVersion: 2,
      }),
    ).toThrow()
  })

  it('keeps all versioned error fixtures in parity with the shared error envelope', () => {
    for (const fixture of errorFixtures) {
      expect(apiErrorContractFixtureSchema.parse(fixture)).toEqual(fixture)
    }
  })

  it('rejects unknown fixture versions and a stale derived namespace', () => {
    expect(() =>
      runtimeContractFixtureSchema.parse({ ...studentRuntimeFixture, fixtureVersion: 2 }),
    ).toThrow()
    expect(() =>
      runtimeContractFixtureSchema.parse({
        ...studentRuntimeFixture,
        browserStorageNamespace: `vmsh-179:v${BROWSER_STORAGE_NAMESPACE_VERSION}:student:human`,
      }),
    ).toThrow()
  })

  it('fetches only the expected audience runtime with credentials and validates it', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify(studentRuntimeFixture.response), {
          headers: { 'Content-Type': 'application/json' },
          status: 200,
        }),
      ),
    )

    const runtime = await fetchRuntime('student', { fetchImplementation })

    expect(runtime.audience).toBe('student')
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith('/student/api/v1/runtime', {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
  })

  it('turns a valid non-success envelope into a correlated API error', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify(unauthenticatedErrorFixture.response), {
          headers: { 'Content-Type': 'application/json' },
          status: unauthenticatedErrorFixture.httpStatus,
        }),
      ),
    )

    const request = fetchRuntime('student', { fetchImplementation })
    await expect(request).rejects.toMatchObject({
      name: 'ApiResponseError',
      status: 401,
      code: 'authentication_required',
      requestId: 'fixture-error-unauthenticated-v1',
    } satisfies Partial<ApiResponseError>)
  })

  it('keeps additive API error metadata compatible during a rolling deploy', () => {
    const parsed = apiErrorContractFixtureSchema.parse({
      ...unauthenticatedErrorFixture,
      response: {
        ...unauthenticatedErrorFixture.response,
        futureEnvelopeMetadata: true,
        error: {
          ...unauthenticatedErrorFixture.response.error,
          futureErrorMetadata: 'ignored by v1',
        },
      },
    })

    expect(parsed).toEqual(unauthenticatedErrorFixture)
  })

  it('rejects realtime events without cursor', () => {
    expect(() =>
      realtimeEventSchema.parse({ type: 'pong', serverTime: '2026-07-22T12:00:00Z' }),
    ).toThrow()
  })

  it('keeps post-upgrade WebSocket errors on the realtime contract', () => {
    expect(realtimeEventSchema.parse(invalidJsonRealtimeFixture.response)).toEqual(
      invalidJsonRealtimeFixture.response,
    )
  })

  it('keeps stable query keys and audience-isolated server-owned sessions', () => {
    expect(queryKeys.task('21n.6a')).toEqual(['tasks', '21n.6a'])
    expect(sessionPolicy.expiryAuthority).toBe('server')
    expect(sessionPolicy.cookieNames.student.access).not.toBe(
      sessionPolicy.cookieNames.family.access,
    )
  })

  it('accepts an audience-scoped invalidation', () => {
    const event = realtimeEventSchema.parse({
      type: 'invalidate',
      audience: 'staff',
      cursor: 3,
      serverTime: '2026-07-22T12:00:00Z',
      resources: ['review-queue'],
      reason: 'submission-updated',
    })
    expect(event.type).toBe('invalidate')
    if (event.type !== 'invalidate') throw new Error('Expected invalidation event')
    expect(event.audience).toBe('staff')
  })

  it('validates offline timing and content identity independently', () => {
    expect(
      offlineMutationSchema.parse({
        idempotencyKey: '123e4567-e89b-42d3-a456-426614174000',
        payloadHash: 'sha256:0123456789abcdef',
        createdAtClient: '2026-07-26T09:59:00Z',
        timezoneOffsetMinutes: -180,
      }).payloadHash,
    ).toBe('sha256:0123456789abcdef')
    expect(lessonDeadlinePolicy.authoringTimeZone).toBe('Europe/Moscow')
    expect(lessonDeadlinePolicy.suspiciousClockSkewMinutes).toBeNull()
    expect(submissionImagePolicy.maximumLongEdgePixels).toBe(1920)
  })
})
