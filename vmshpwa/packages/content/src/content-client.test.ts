import { describe, expect, it, vi } from 'vitest'

import fixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import {
  contentEtagSchema,
  runtimeBoundaryByAudience,
  type Audience,
  type RuntimeConfig,
} from '@vmsh/contracts'

import { ContentProtocolError, createContentApiClient } from './content-client'

function runtime(audience: Audience): RuntimeConfig {
  return {
    contractVersion: 1,
    audience,
    ...runtimeBoundaryByAudience[audience],
    instance: 'content-client-test',
    serverTime: '2026-07-27T10:00:00Z',
    requestId: 'runtime-test',
    features: { telegram: false, google: false, nats: false, prototype: false },
  }
}

const revision = {
  revisionId: fixture.document.revisionId,
  sourceId: 'content-source-41-condition',
  groupLessonId: 'group-lesson-41-n',
  courseId: 'course-math-5-7',
  groupId: 'group-beginner',
  kind: 'condition',
  logicalFilename: 'lesson-41/condition.tex',
  revisionNumber: 1,
  status: 'ready',
  version: 2,
  compileLeaseExpiresAt: null,
  compileAttempt: 1,
  sourceSha256: fixture.document.sourceSha256,
  parserVersion: 'vmsh-content-1',
  diagnostics: [],
  missingAssets: [],
  requestId: 'content-test',
} as const

function jsonResponse(body: unknown, init: ResponseInit & { etag?: string } = {}): Response {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (init.etag) headers.set('ETag', init.etag)
  return new Response(JSON.stringify(body), { ...init, headers })
}

function requestUrl(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : input.toString()
}

describe('Content API client', () => {
  it('sends multipart upload and preserves the strong revision ETag for compile', async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = []
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: requestUrl(input), init })
      return Promise.resolve(
        requests.length === 1
          ? jsonResponse(
              { ...revision, status: 'uploaded', version: 1, compileAttempt: 0 },
              {
                status: 201,
                etag: `"${revision.revisionId}:v1"`,
              },
            )
          : jsonResponse(revision, {
              status: 200,
              etag: `"${revision.revisionId}:v2"`,
            }),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    const uploaded = await client.uploadSource({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
      logicalFilename: revision.logicalFilename,
      source: new Blob(['\\задача Тест \\кзадача'], { type: 'text/plain' }),
    })
    await client.compileRevision(uploaded.data.revisionId, uploaded.etag)

    expect(requests[0]?.url).toBe('/staff/api/v1/content/uploads')
    const form = requests[0]?.init?.body
    expect(form).toBeInstanceOf(FormData)
    expect((form as FormData).get('groupLessonId')).toBe(revision.groupLessonId)
    expect((form as FormData).get('kind')).toBe('condition')
    expect(requests[1]?.url).toContain(
      `/content/revisions/${encodeURIComponent(revision.revisionId)}/compile`,
    )
    expect(new Headers(requests[1]?.init?.headers).get('If-Match')).toBe(
      `"${revision.revisionId}:v1"`,
    )
    expect(requests.every((request) => request.init?.credentials === 'include')).toBe(true)
  })

  it('publishes a fresh slot with the explicit none precondition', async () => {
    let requestBody: unknown
    let ifMatch: string | null = null
    const fetchImplementation = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (typeof init?.body !== 'string') throw new TypeError('Expected JSON request body')
      requestBody = JSON.parse(init.body)
      ifMatch = new Headers(init?.headers).get('If-Match')
      return Promise.resolve(
        jsonResponse(
          {
            publicationId: 'publication-41-condition',
            groupLessonId: revision.groupLessonId,
            revisionId: revision.revisionId,
            kind: 'condition',
            state: 'published',
            version: 1,
            scheduledAt: null,
            publishedAt: '2026-07-27T10:01:00Z',
            hiddenAt: null,
            requestId: 'publish-test',
          },
          { status: 201, etag: '"publication-41-condition:v1"' },
        ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await client.publish({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
      revisionId: revision.revisionId,
      mode: 'publish',
    })

    expect(ifMatch).toBe('"none"')
    expect(requestBody).toEqual({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
      revisionId: revision.revisionId,
      mode: 'publish',
      scheduledLocalTime: null,
      businessTimezone: null,
      expectedCurrentPublicationId: null,
      expectedCurrentVersion: null,
      expectedScheduledPublicationId: null,
      expectedScheduledVersion: null,
    })
  })

  it('sends the lesson wall time and authoritative IANA zone without browser conversion', async () => {
    let requestBody: unknown
    const fetchImplementation = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (typeof init?.body !== 'string') throw new TypeError('Expected JSON request body')
      requestBody = JSON.parse(init.body)
      return Promise.resolve(
        jsonResponse(
          {
            publicationId: 'publication-scheduled-41',
            groupLessonId: revision.groupLessonId,
            revisionId: revision.revisionId,
            kind: 'condition',
            state: 'scheduled',
            version: 1,
            scheduledAt: '2026-10-25T10:05:00Z',
            publishedAt: null,
            hiddenAt: null,
            requestId: 'schedule-test',
          },
          { status: 201, etag: '"publication-scheduled-41:v1"' },
        ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await client.publish({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
      revisionId: revision.revisionId,
      mode: 'schedule',
      scheduledLocalTime: '2026-10-25T13:05',
      businessTimezone: 'Europe/Moscow',
    })

    expect(requestBody).toMatchObject({
      scheduledLocalTime: '2026-10-25T13:05',
      businessTimezone: 'Europe/Moscow',
    })
  })

  it('publishes and rolls back against exact published and scheduled slots', async () => {
    const requests: Array<{ url: string; body: unknown; ifMatch: string | null }> = []
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({
        url: requestUrl(input),
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : init?.body,
        ifMatch: new Headers(init?.headers).get('If-Match'),
      })
      return Promise.resolve(
        jsonResponse(
          {
            publicationId: `publication-result-${requests.length}`,
            groupLessonId: revision.groupLessonId,
            revisionId: revision.revisionId,
            kind: 'condition',
            state: 'published',
            version: 1,
            scheduledAt: null,
            publishedAt: '2026-07-27T10:01:00Z',
            hiddenAt: null,
            requestId: `dual-slot-${requests.length}`,
          },
          { status: 201, etag: `"publication-result-${requests.length}:v1"` },
        ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })
    const current = {
      publicationId: 'publication-current',
      version: 2,
      etag: contentEtagSchema.parse('"publication-current:v2"'),
    }
    const scheduled = {
      publicationId: 'publication-scheduled',
      version: 4,
      etag: contentEtagSchema.parse('"publication-scheduled:v4"'),
    }

    await client.publish({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
      revisionId: revision.revisionId,
      mode: 'publish',
      current,
      scheduled,
    })
    await client.rollback(current, revision.revisionId, scheduled)

    expect(requests[0]).toMatchObject({
      url: '/staff/api/v1/publications',
      ifMatch: '"publication-current:v2"',
      body: {
        expectedCurrentPublicationId: 'publication-current',
        expectedCurrentVersion: 2,
        expectedScheduledPublicationId: 'publication-scheduled',
        expectedScheduledVersion: 4,
      },
    })
    expect(requests[1]).toMatchObject({
      url: '/staff/api/v1/publications/publication-current/rollback',
      ifMatch: '"publication-current:v2"',
      body: {
        revisionId: revision.revisionId,
        expectedScheduledPublicationId: 'publication-scheduled',
        expectedScheduledVersion: 4,
      },
    })
  })

  it('hides only the exact published resource', async () => {
    let request: { url: string; body: BodyInit | null | undefined; ifMatch: string | null } | null =
      null
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      request = {
        url: requestUrl(input),
        body: init?.body,
        ifMatch: new Headers(init?.headers).get('If-Match'),
      }
      return Promise.resolve(
        jsonResponse(
          {
            publicationId: 'publication-current',
            groupLessonId: revision.groupLessonId,
            revisionId: revision.revisionId,
            kind: 'condition',
            state: 'hidden',
            version: 3,
            scheduledAt: null,
            publishedAt: '2026-07-27T10:01:00Z',
            hiddenAt: '2026-07-27T10:05:00Z',
            action: 'hidden',
            requestId: 'hide-test',
          },
          { etag: '"publication-current:v3"' },
        ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await client.hidePublished({
      publicationId: 'publication-current',
      version: 2,
      etag: contentEtagSchema.parse('"publication-current:v2"'),
    })

    expect(request).toEqual({
      url: '/staff/api/v1/publications/publication-current/hide',
      body: '{}',
      ifMatch: '"publication-current:v2"',
    })
  })

  it('restores three material slots and cancels only the exact scheduled publication', async () => {
    const requests: Array<{
      url: string
      body: BodyInit | null | undefined
      ifMatch: string | null
    }> = []
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({
        url: requestUrl(input),
        body: init?.body,
        ifMatch: new Headers(init?.headers).get('If-Match'),
      })
      if (requests.length === 1) {
        return Promise.resolve(
          jsonResponse({
            groupLessonId: revision.groupLessonId,
            courseId: revision.courseId,
            groupId: revision.groupId,
            businessTimezone: 'Europe/Moscow',
            materials: ['condition', 'hint', 'solution'].map((kind) => ({
              kind,
              revisions: [],
              currentPublished: null,
              currentScheduled: null,
              publicationHistory: [],
            })),
            requestId: 'history-client-test',
          }),
        )
      }
      return Promise.resolve(
        jsonResponse(
          {
            publicationId: 'publication-scheduled-41',
            groupLessonId: revision.groupLessonId,
            revisionId: revision.revisionId,
            kind: 'condition',
            state: 'superseded',
            version: 2,
            scheduledAt: '2026-07-28T10:00:00Z',
            publishedAt: null,
            hiddenAt: null,
            action: 'cancelled',
            requestId: 'cancel-client-test',
          },
          { etag: '"publication-scheduled-41:v2"' },
        ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await client.history(revision.groupLessonId)
    await client.cancelScheduled({
      publicationId: 'publication-scheduled-41',
      version: 1,
      etag: contentEtagSchema.parse('"publication-scheduled-41:v1"'),
    })

    expect(requests[0]?.url).toBe(
      `/staff/api/v1/publications?groupLesson=${revision.groupLessonId}`,
    )
    expect(requests[1]?.body).toBe('{}')
    expect(requests[1]?.ifMatch).toBe('"publication-scheduled-41:v1"')
  })

  it('keeps Student and Family URLs owner-scoped and validates public content', async () => {
    const urls: string[] = []
    const published = {
      groupLessonId: revision.groupLessonId,
      courseId: revision.courseId,
      groupId: revision.groupId,
      kind: 'condition',
      publicationId: 'publication-41-condition',
      publicationVersion: 1,
      publishedAt: '2026-07-27T10:01:00Z',
      revisionId: revision.revisionId,
      document: fixture.document,
    }
    const fetchImplementation = vi.fn((input: RequestInfo | URL) => {
      urls.push(requestUrl(input))
      return Promise.resolve(jsonResponse(published))
    }) as typeof fetch

    await createContentApiClient(runtime('student'), { fetchImplementation }).published({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
    })
    await createContentApiClient(runtime('family'), { fetchImplementation }).published({
      groupLessonId: revision.groupLessonId,
      kind: 'condition',
      studentPublicId: 'student-179',
    })

    expect(urls).toEqual([
      `/student/api/v1/group-lessons/${revision.groupLessonId}/content/condition`,
      `/family/api/v1/children/student-179/group-lessons/${revision.groupLessonId}/content/condition`,
    ])
  })

  it('refreshes once on 401 and rejects an invalid success envelope', async () => {
    const refreshSession = vi.fn(() => Promise.resolve(undefined))
    let attempt = 0
    const fetchImplementation = vi.fn(() => {
      attempt += 1
      if (attempt === 1) {
        return Promise.resolve(
          jsonResponse(
            {
              error: {
                code: 'authentication_required',
                message: 'Войдите снова',
                requestId: 'expired-test',
              },
            },
            { status: 401 },
          ),
        )
      }
      return Promise.resolve(jsonResponse({ unexpected: true }))
    }) as typeof fetch
    const client = createContentApiClient(runtime('student'), {
      fetchImplementation,
      refreshSession,
    })

    await expect(
      client.published({ groupLessonId: revision.groupLessonId, kind: 'condition' }),
    ).rejects.toBeInstanceOf(ContentProtocolError)
    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })
})
