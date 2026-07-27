import { describe, expect, it } from 'vitest'

import contentFixture from '../fixtures/content/web-document.v1.json'
import {
  contentEtagSchema,
  contentQueryKeys,
  publishContentRequestSchema,
  publishedContentSchema,
  rollbackContentRequestSchema,
  staffContentHistorySchema,
  staffContentPreviewSchema,
  staffContentRevisionSchema,
} from './content-api'

const document = contentFixture.document

describe('Phase-2 content HTTP contracts', () => {
  it('accepts the bounded Staff revision projection', () => {
    const revision = staffContentRevisionSchema.parse({
      revisionId: document.revisionId,
      sourceId: 'content-source-41-condition',
      groupLessonId: 'group-lesson-41-n',
      courseId: 'course-math-5-7',
      groupId: 'group-beginner',
      kind: 'condition',
      logicalFilename: 'lesson-41/condition.tex',
      revisionNumber: 3,
      status: 'ready',
      version: 3,
      compileLeaseExpiresAt: null,
      compileAttempt: 1,
      sourceSha256: document.sourceSha256,
      parserVersion: 'vmsh-content-1',
      diagnostics: [
        {
          code: 'latex.layout_crosses_semantic_boundary',
          severity: 'warning',
          message: 'Команда вёрстки пропущена.',
          span: {
            source_name: 'lesson-41/condition.tex',
            start: { offset: 12, line: 2, column: 1 },
            end: { offset: 16, line: 2, column: 5 },
          },
          recovery: null,
        },
      ],
      missingAssets: ['figures/rook.svg'],
      requestId: 'contract-test',
    })

    expect(revision.status).toBe('ready')
    expect(revision.sourceId).toBe('content-source-41-condition')
    expect(revision.compileAttempt).toBe(1)
    expect(revision.diagnostics[0]?.span.start.line).toBe(2)
  })

  it('counts Telegram Rich HTML in Unicode characters rather than UTF-16 code units', () => {
    const boundary = '📚'.repeat(32_768)

    expect(
      staffContentPreviewSchema.parse({
        revisionId: document.revisionId,
        kind: 'telegram',
        html: boundary,
      }),
    ).toMatchObject({ html: boundary })
    expect(() =>
      staffContentPreviewSchema.parse({
        revisionId: document.revisionId,
        kind: 'telegram',
        html: `${boundary}📚`,
      }),
    ).toThrow()
  })

  it('rejects preview and published envelopes whose revision or kind diverges', () => {
    expect(() =>
      staffContentPreviewSchema.parse({
        revisionId: 'revision:other',
        kind: 'web',
        document,
      }),
    ).toThrow()

    expect(() =>
      publishedContentSchema.parse({
        groupLessonId: 'group-lesson-41-n',
        courseId: 'course-math-5-7',
        groupId: 'group-beginner',
        kind: 'solution',
        publicationId: 'publication-1',
        publicationVersion: 1,
        publishedAt: '2026-01-26T13:00:00Z',
        revisionId: document.revisionId,
        document,
      }),
    ).toThrow()
  })

  it('keeps ETags and audience/owner query keys exact', () => {
    expect(contentEtagSchema.parse('"content-revision-1:v3"')).toBe('"content-revision-1:v3"')
    expect(() => contentEtagSchema.parse('content-revision-1:v3')).toThrow()
    expect(contentQueryKeys.published('family', 'lesson-41', 'hint', 'student-1')).toEqual([
      'content',
      'published',
      'family',
      'lesson-41',
      'hint',
      'student-1',
    ])
  })

  it('requires complete optimistic pairs for both publication slots', () => {
    expect(
      publishContentRequestSchema.parse({
        groupLessonId: 'group-lesson-41-n',
        kind: 'condition',
        revisionId: document.revisionId,
        mode: 'publish',
        scheduledLocalTime: null,
        businessTimezone: null,
        expectedCurrentPublicationId: 'publication-current',
        expectedCurrentVersion: 2,
        expectedScheduledPublicationId: 'publication-scheduled',
        expectedScheduledVersion: 4,
      }),
    ).toMatchObject({ expectedCurrentVersion: 2, expectedScheduledVersion: 4 })
    expect(() =>
      publishContentRequestSchema.parse({
        groupLessonId: 'group-lesson-41-n',
        kind: 'condition',
        revisionId: document.revisionId,
        mode: 'schedule',
        scheduledLocalTime: '2026-07-28T13:00',
        businessTimezone: 'Europe/Moscow',
        expectedCurrentPublicationId: 'publication-scheduled',
        expectedCurrentVersion: 4,
        expectedScheduledPublicationId: null,
        expectedScheduledVersion: null,
      }),
    ).toThrow()
    expect(() =>
      rollbackContentRequestSchema.parse({
        revisionId: document.revisionId,
        expectedScheduledPublicationId: 'publication-scheduled',
        expectedScheduledVersion: null,
      }),
    ).toThrow()
  })

  it('requires one owner-scoped history slot for every independent material', () => {
    const material = (kind: 'condition' | 'hint' | 'solution') => ({
      kind,
      revisions: [],
      currentPublished: null,
      currentScheduled: null,
      publicationHistory: [],
    })
    const response = {
      groupLessonId: 'group-lesson-41-n',
      courseId: 'course-math-5-7',
      groupId: 'group-beginner',
      businessTimezone: 'Europe/Moscow',
      materials: [material('condition'), material('hint'), material('solution')],
      requestId: 'history-test',
    }

    expect(staffContentHistorySchema.parse(response).materials).toHaveLength(3)
    expect(() =>
      staffContentHistorySchema.parse({
        ...response,
        materials: [material('condition'), material('condition'), material('solution')],
      }),
    ).toThrow()
    expect(() =>
      staffContentHistorySchema.parse({
        ...response,
        materials: [
          {
            ...material('condition'),
            currentPublished: {
              publicationId: 'publication-scheduled',
              revisionId: document.revisionId,
              kind: 'condition',
              state: 'scheduled',
              version: 1,
              scheduledAt: '2026-07-28T10:00:00Z',
              publishedAt: null,
              hiddenAt: null,
              etag: '"publication-scheduled:v1"',
            },
          },
          material('hint'),
          material('solution'),
        ],
      }),
    ).toThrow()
  })

  it('requires exact local calendar time and a valid IANA business timezone', () => {
    const request = {
      groupLessonId: 'group-lesson-41-n',
      kind: 'condition',
      revisionId: document.revisionId,
      mode: 'schedule',
      scheduledLocalTime: '2026-07-28T13:05',
      businessTimezone: 'Europe/Moscow',
      expectedCurrentPublicationId: null,
      expectedCurrentVersion: null,
      expectedScheduledPublicationId: null,
      expectedScheduledVersion: null,
    } as const

    expect(publishContentRequestSchema.parse(request)).toMatchObject({
      scheduledLocalTime: '2026-07-28T13:05',
      businessTimezone: 'Europe/Moscow',
    })
    expect(() =>
      publishContentRequestSchema.parse({ ...request, scheduledLocalTime: '2026-02-30T13:05' }),
    ).toThrow()
    expect(() =>
      publishContentRequestSchema.parse({ ...request, businessTimezone: 'browser-local' }),
    ).toThrow()
  })
})
