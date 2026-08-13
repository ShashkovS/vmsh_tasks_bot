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

const reviewEtag = '"review-content-revision-41:v1"'
const matchReview = {
  revisionId: revision.revisionId,
  groupLessonId: revision.groupLessonId,
  version: 1,
  etag: reviewEtag,
  items: [
    {
      sourceOrdinal: 1,
      sourceItem: '1',
      displayNumber: '1',
      sourceTitle: 'Орехи',
      suggestedProblemId: -41,
      match: null,
    },
  ],
  candidates: [
    {
      problemId: -41,
      problemNumber: 1,
      item: '',
      title: 'Сколько орехов',
      problemType: 1,
      answerType: 2,
      answerValidation: null,
      validationError: null,
      correctAnswer: '7',
      correctAnswerChecker: null,
      wrongAnswer: 'Нет, не столько орехов',
      congratulation: 'Да, всё верно!',
    },
  ],
  requestId: 'problem-review-test',
} as const

const metadataGrid = {
  revisionId: revision.revisionId,
  groupLessonId: revision.groupLessonId,
  version: 1,
  etag: reviewEtag,
  rows: [
    {
      problemId: -41,
      sourceOrdinal: 1,
      sourceItem: '1',
      displayNumber: '1',
      title: 'Сколько орехов',
      problemType: 1,
      answerType: 2,
      answerValidation: null,
      validationError: 'Введите число орехов, например 7',
      correctAnswer: '7',
      correctAnswerChecker: null,
      wrongAnswer: 'Нет, не столько орехов',
      congratulation: 'Да, всё верно!',
      reviewed: false,
    },
  ],
  requestId: 'metadata-grid-test',
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
  it('loads and updates the independent lesson cutoff', async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = []
    const window = {
      lessonWindowId: 'lesson-window-1',
      groupLessonId: revision.groupLessonId,
      opensAt: '2026-09-06T13:00:00Z',
      submissionClosesAt: '2026-09-12T17:50:00Z',
      hintScheduledAt: null,
      solutionScheduledAt: '2026-09-12T18:00:00Z',
      businessTimezone: 'Europe/Moscow',
      source: 'native',
      version: 1,
      requestId: 'window-test',
    } as const
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: requestUrl(input), init })
      return Promise.resolve(jsonResponse(window, { etag: '"lesson-window-1:v1"' }))
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    const loaded = await client.lessonWindow!(revision.groupLessonId)
    await client.updateSubmissionCutoff!(revision.groupLessonId, loaded.etag, {
      submissionClosesLocalTime: '2026-09-12T20:50',
      businessTimezone: 'Europe/Moscow',
      confirmChange: true,
    })

    expect(requests[0]?.url).toBe(
      `/staff/api/v1/group-lessons/${revision.groupLessonId}/lesson-window`,
    )
    expect(requests[1]?.url).toContain('/lesson-window/submission-cutoff')
    expect(new Headers(requests[1]?.init?.headers).get('If-Match')).toBe('"lesson-window-1:v1"')
  })

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

  it('loads only validated sibling group lessons as bulk upload targets', async () => {
    const payload = {
      courseLessonId: 'course-lesson-41',
      courseId: 'course-math',
      courseName: 'Математика 5–7',
      lessonNumber: 41,
      targets: [
        {
          groupLessonId: revision.groupLessonId,
          groupId: revision.groupId,
          groupName: 'Начинающие',
          groupShortCode: 'n',
          colorKey: 'beginner',
          status: 'active',
        },
      ],
      requestId: 'content-client-upload-targets',
    }
    const fetchImplementation = vi.fn(() => Promise.resolve(jsonResponse(payload)))
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await expect(client.uploadTargets(revision.groupLessonId)).resolves.toEqual(payload)
    expect(fetchImplementation).toHaveBeenCalledWith(
      `/staff/api/v1/content/group-lessons/${revision.groupLessonId}/upload-targets`,
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )

    const invalidClient = createContentApiClient(runtime('staff'), {
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          jsonResponse({ ...payload, targets: [payload.targets[0], payload.targets[0]] }),
        ),
      ),
    })
    await expect(invalidClient.uploadTargets(revision.groupLessonId)).rejects.toBeInstanceOf(
      ContentProtocolError,
    )
  })

  it('lists exact revision assets and uploads files under the latest revision ETag', async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = []
    const asset = {
      assetId: 'asset-rook',
      contentSha256: 'b'.repeat(64),
      src: '/pwa-content-assets/asset-rook',
      mediaType: 'image/webp',
      width: 1280,
      height: 720,
    } as const
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: requestUrl(input), init })
      return Promise.resolve(
        requests.length === 1
          ? jsonResponse(
              {
                revisionId: revision.revisionId,
                status: 'uploaded',
                version: 2,
                missingAssets: ['figures/rook.png'],
                assets: [
                  {
                    logicalName: 'figures/rook.png',
                    sourceKind: 'figure',
                    status: 'missing',
                    acceptedUploadKinds: ['raster', 'svg'],
                    asset: null,
                  },
                ],
                requestId: 'asset-list-test',
              },
              { etag: `W/"${revision.revisionId}:v2"` },
            )
          : jsonResponse(
              {
                revisionId: revision.revisionId,
                status: 'uploaded',
                version: 3,
                logicalName: 'figures/rook.png',
                sourceKind: 'figure',
                asset,
                reused: false,
                requestId: 'asset-upload-test',
              },
              { status: 201, etag: `"${revision.revisionId}:v3"` },
            ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    const listed = await client.revisionAssets(revision.revisionId)
    expect(listed.etag).toBe(`"${revision.revisionId}:v2"`)
    const file = new File(['image'], 'rook.png', { type: 'image/png' })
    await client.uploadRevisionAsset({
      revisionId: revision.revisionId,
      etag: listed.etag,
      logicalName: 'figures/rook.png',
      kind: 'raster',
      asset: file,
    })

    expect(requests[0]?.url).toBe(
      `/staff/api/v1/content/revisions/${encodeURIComponent(revision.revisionId)}/assets`,
    )
    expect(requests[1]?.url).toBe(requests[0]?.url)
    expect(new Headers(requests[1]?.init?.headers).get('If-Match')).toBe(
      `"${revision.revisionId}:v2"`,
    )
    const form = requests[1]?.init?.body
    expect(form).toBeInstanceOf(FormData)
    expect((form as FormData).get('logicalName')).toBe('figures/rook.png')
    expect((form as FormData).get('kind')).toBe('raster')
    expect((form as FormData).get('asset')).toBeInstanceOf(File)
  })

  it('generates TikZ from the stored revision without sending a browser file', async () => {
    let body: FormData | undefined
    const fetchImplementation = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      body = init?.body as FormData
      return Promise.resolve(
        jsonResponse(
          {
            revisionId: revision.revisionId,
            status: 'uploaded',
            version: 4,
            logicalName: 'tikz/diagram-1',
            sourceKind: 'tikz',
            asset: {
              assetId: 'asset-diagram-1',
              contentSha256: 'c'.repeat(64),
              src: 'https://assets.example.test/content/diagram-1.svg',
              mediaType: 'image/svg+xml',
              width: 640,
              height: 360,
            },
            reused: true,
            requestId: 'tikz-upload-test',
          },
          { etag: `"${revision.revisionId}:v4"` },
        ),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await client.uploadRevisionAsset({
      revisionId: revision.revisionId,
      etag: contentEtagSchema.parse(`"${revision.revisionId}:v3"`),
      logicalName: 'tikz/diagram-1',
      kind: 'tikz',
    })

    expect(body?.get('logicalName')).toBe('tikz/diagram-1')
    expect(body?.get('kind')).toBe('tikz')
    expect(body?.has('asset')).toBe(false)
    await expect(
      client.uploadRevisionAsset({
        revisionId: revision.revisionId,
        etag: contentEtagSchema.parse(`"${revision.revisionId}:v3"`),
        logicalName: 'figures/rook.svg',
        kind: 'svg',
      }),
    ).rejects.toThrow('require a file')
  })

  it('loads an authenticated persisted PDF descriptor without accepting an external URL', async () => {
    const expected = {
      revisionId: revision.revisionId,
      kind: 'pdf' as const,
      src: `/staff/api/v1/content/revisions/${revision.revisionId}/pdf`,
      contentSha256: 'd'.repeat(64),
      byteSize: 42_179,
      rendererVersion: 'vmsh-content-pdf/1',
    }
    const fetchImplementation = vi.fn(() => Promise.resolve(jsonResponse(expected))) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await expect(client.preview(revision.revisionId, 'pdf')).resolves.toEqual(expected)
    expect(fetchImplementation).toHaveBeenCalledWith(
      `/staff/api/v1/content/revisions/${encodeURIComponent(revision.revisionId)}/previews/pdf`,
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )

    const invalidClient = createContentApiClient(runtime('staff'), {
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          jsonResponse({ ...expected, src: 'https://untrusted.example.test/condition.pdf' }),
        ),
      ),
    })
    await expect(invalidClient.preview(revision.revisionId, 'pdf')).rejects.toBeInstanceOf(
      ContentProtocolError,
    )
  })

  it('loads and atomically saves the complete problem-matching batch', async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = []
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: requestUrl(input), init })
      const body =
        requests.length === 1
          ? matchReview
          : {
              ...matchReview,
              version: 2,
              etag: '"review-content-revision-41:v2"',
              items: [
                {
                  ...matchReview.items[0],
                  match: { decision: 'manual_match', problemId: -41 },
                },
              ],
            }
      return Promise.resolve(
        jsonResponse(body, {
          etag: body.etag,
        }),
      )
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    const loaded = await client.problemMatches(revision.revisionId)
    const saved = await client.resolveProblemMatches({
      revisionId: revision.revisionId,
      etag: loaded.etag,
      matches: [
        {
          sourceOrdinal: 1,
          sourceItem: '1',
          decision: 'manual_match',
          problemId: -41,
        },
      ],
    })

    const expectedPath = `/staff/api/v1/content/revisions/${encodeURIComponent(revision.revisionId)}/problem-matches`
    expect(requests.map((request) => request.url)).toEqual([expectedPath, expectedPath])
    expect(requests[1]?.init?.method).toBe('PUT')
    expect(new Headers(requests[1]?.init?.headers).get('If-Match')).toBe(reviewEtag)
    expect(JSON.parse(requests[1]?.init?.body as string)).toEqual({
      matches: [
        {
          sourceOrdinal: 1,
          sourceItem: '1',
          decision: 'manual_match',
          problemId: -41,
        },
      ],
    })
    expect(saved.data.items[0]?.match?.problemId).toBe(-41)
  })

  it('loads condition metadata by revision and saves a reviewed grid', async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = []
    const fetchImplementation = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: requestUrl(input), init })
      const body =
        requests.length === 1
          ? metadataGrid
          : {
              ...metadataGrid,
              version: 2,
              etag: '"review-content-revision-41:v2"',
              rows: [{ ...metadataGrid.rows[0], reviewed: true }],
            }
      return Promise.resolve(jsonResponse(body, { etag: body.etag }))
    }) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    const loaded = await client.metadataGrid(revision.groupLessonId, revision.revisionId)
    const row = loaded.data.rows[0]!
    const saved = await client.saveMetadataGrid({
      groupLessonId: revision.groupLessonId,
      revisionId: revision.revisionId,
      etag: loaded.etag,
      rows: [
        {
          problemId: row.problemId,
          sourceOrdinal: row.sourceOrdinal,
          sourceItem: row.sourceItem,
          displayNumber: row.displayNumber,
          title: row.title,
          problemType: row.problemType,
          answerType: row.answerType,
          answerValidation: row.answerValidation,
          validationError: row.validationError,
          correctAnswer: row.correctAnswer,
          correctAnswerChecker: row.correctAnswerChecker,
          wrongAnswer: row.wrongAnswer,
          congratulation: row.congratulation,
        },
      ],
    })

    expect(requests[0]?.url).toBe(
      `/staff/api/v1/group-lessons/${revision.groupLessonId}/metadata-grid?revisionId=${encodeURIComponent(revision.revisionId)}`,
    )
    expect(requests[1]?.url).toBe(
      `/staff/api/v1/group-lessons/${revision.groupLessonId}/metadata-grid`,
    )
    expect(requests[1]?.init?.method).toBe('PUT')
    expect(new Headers(requests[1]?.init?.headers).get('If-Match')).toBe(reviewEtag)
    expect(JSON.parse(requests[1]?.init?.body as string)).not.toHaveProperty('rows.0.reviewed')
    expect(saved.data.rows[0]?.reviewed).toBe(true)
  })

  it('rejects contradictory batches and mismatched review ETags before state can drift', async () => {
    const fetchImplementation = vi.fn(() =>
      Promise.resolve(jsonResponse(matchReview, { etag: '"review-content-revision-41:v2"' })),
    ) as typeof fetch
    const client = createContentApiClient(runtime('staff'), { fetchImplementation })

    await expect(client.problemMatches(revision.revisionId)).rejects.toBeInstanceOf(
      ContentProtocolError,
    )
    await expect(
      client.resolveProblemMatches({
        revisionId: revision.revisionId,
        etag: contentEtagSchema.parse(reviewEtag),
        matches: [
          {
            sourceOrdinal: 1,
            sourceItem: '1',
            decision: 'omit',
            problemId: -41,
          },
        ],
      }),
    ).rejects.toThrow('New and omitted problems cannot carry a problem ID')
    expect(fetchImplementation).toHaveBeenCalledTimes(1)
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
    await expect(
      createContentApiClient(runtime('student'), { fetchImplementation }).published({
        groupLessonId: revision.groupLessonId,
        kind: 'hint',
      }),
    ).rejects.toThrow('audited problem reveal')
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

  it('audits one Student problem reveal through an exact JSON POST', async () => {
    const hintDocument = {
      ...fixture.document,
      materialKind: 'hint',
      introduction: [],
      problems: [fixture.document.problems[0]],
    }
    const revealed = {
      groupLessonId: revision.groupLessonId,
      courseId: revision.courseId,
      groupId: revision.groupId,
      kind: 'hint',
      publicationId: 'publication-41-hint',
      publicationVersion: 1,
      publishedAt: '2026-07-27T10:01:00Z',
      revisionId: revision.revisionId,
      problemId: 'problem-41-n-1',
      sourceOrdinal: 1,
      revealedAt: '2026-07-27T10:02:00Z',
      firstReveal: true,
      document: hintDocument,
    }
    const fetchImplementation = vi.fn<typeof fetch>(() => Promise.resolve(jsonResponse(revealed)))
    const client = createContentApiClient(runtime('student'), { fetchImplementation })

    await expect(
      client.revealStudentProblemMaterial({
        groupLessonId: revision.groupLessonId,
        problemId: revealed.problemId,
        kind: 'hint',
      }),
    ).resolves.toEqual(revealed)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      `/student/api/v1/group-lessons/${revision.groupLessonId}/problems/${revealed.problemId}/reveal/hint`,
    )
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: '{}',
      credentials: 'include',
    })

    const family = createContentApiClient(runtime('family'), { fetchImplementation })
    await expect(
      family.revealStudentProblemMaterial({
        groupLessonId: revision.groupLessonId,
        problemId: revealed.problemId,
        kind: 'hint',
      }),
    ).rejects.toThrow('Only Student')
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
