import { describe, expect, it } from 'vitest'

import contentFixture from '../fixtures/content/web-document.v1.json'
import {
  contentAssetsMissingDetailsSchema,
  contentEtagSchema,
  contentQueryKeys,
  historicalAnswerTypeValues,
  problemMatchMutationRequestSchema,
  problemMatchReviewSchema,
  problemMetadataGridSchema,
  problemMetadataMutationRequestSchema,
  publishContentRequestSchema,
  publishedContentSchema,
  rollbackContentRequestSchema,
  staffContentHistorySchema,
  staffContentAssetResolveSchema,
  staffContentAssetUploadSchema,
  staffContentPreviewSchema,
  staffContentRevisionAssetsSchema,
  staffContentRevisionSchema,
  staffContentUploadTargetsSchema,
  studentProblemRevealSchema,
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

  it('accepts bounded unique group-lesson targets for explicit bulk upload', () => {
    const targets = staffContentUploadTargetsSchema.parse({
      courseLessonId: 'course-lesson-41',
      courseId: 'course-math',
      courseName: 'Математика 5–7',
      lessonNumber: 41,
      targets: [
        {
          groupLessonId: 'group-lesson-41-n',
          groupId: 'group-beginner',
          groupName: 'Начинающие',
          groupShortCode: 'n',
          colorKey: 'beginner',
          status: 'active',
        },
        {
          groupLessonId: 'group-lesson-41-p',
          groupId: 'group-continuing',
          groupName: 'Продолжающие',
          groupShortCode: 'p',
          colorKey: null,
          status: 'draft',
        },
      ],
      requestId: 'contract-upload-targets',
    })

    expect(targets.targets).toHaveLength(2)
    expect(contentQueryKeys.uploadTargets('group-lesson-41-n')).toEqual([
      'content',
      'upload-targets',
      'group-lesson-41-n',
    ])
    expect(() =>
      staffContentUploadTargetsSchema.parse({
        ...targets,
        targets: [targets.targets[0], targets.targets[0]],
      }),
    ).toThrow()
  })

  it('accepts only bounded same-origin Staff PDF preview descriptors', () => {
    const preview = staffContentPreviewSchema.parse({
      revisionId: document.revisionId,
      kind: 'pdf',
      src: `/staff/api/v1/content/revisions/${document.revisionId}/pdf`,
      contentSha256: 'd'.repeat(64),
      byteSize: 42_179,
      rendererVersion: 'vmsh-content-pdf/1',
    })

    expect(preview.kind).toBe('pdf')
    expect(() =>
      staffContentPreviewSchema.parse({
        ...preview,
        src: 'https://untrusted.example.test/condition.pdf',
      }),
    ).toThrow()
    expect(() =>
      staffContentPreviewSchema.parse({
        ...preview,
        byteSize: 65 * 1024 * 1024,
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

  it('accepts only one exact audited problem material in a reveal response', () => {
    const hintDocument = {
      ...document,
      materialKind: 'hint',
      introduction: [],
      problems: [document.problems[0]],
    }
    const reveal = studentProblemRevealSchema.parse({
      groupLessonId: 'group-lesson-41-n',
      courseId: 'course-math-5-7',
      groupId: 'group-beginner',
      kind: 'hint',
      publicationId: 'publication-41-hint',
      publicationVersion: 1,
      publishedAt: '2026-01-28T09:00:00Z',
      revisionId: document.revisionId,
      problemId: 'problem-41-n-1',
      sourceOrdinal: document.problems[0]?.ordinal,
      revealedAt: '2026-01-28T10:00:00Z',
      firstReveal: true,
      document: hintDocument,
    })

    expect(reveal.document.problems).toHaveLength(1)
    expect(() =>
      studentProblemRevealSchema.parse({
        ...reveal,
        document: { ...hintDocument, introduction: document.introduction },
      }),
    ).toThrow()
    expect(() => studentProblemRevealSchema.parse({ ...reveal, kind: 'solution' })).toThrow()
  })

  it('keeps ETags and audience/owner query keys exact', () => {
    expect(contentEtagSchema.parse('"content-revision-1:v3"')).toBe('"content-revision-1:v3"')
    expect(() => contentEtagSchema.parse('content-revision-1:v3')).toThrow()
    expect(
      contentQueryKeys.published(
        { audience: 'family', accountId: 'account-family-1' },
        'lesson-41',
        'hint',
        'student-1',
      ),
    ).toEqual([
      'principal',
      'family',
      'account-family-1',
      'content',
      'published',
      'lesson-41',
      'hint',
      'student-1',
    ])
    expect(contentQueryKeys.assets(document.revisionId)).toEqual([
      'content',
      'assets',
      document.revisionId,
    ])
  })

  it('keeps missing and attached revision assets internally consistent', () => {
    expect(
      contentAssetsMissingDetailsSchema.parse({ missingAssets: ['figures/rook.svg'] }),
    ).toEqual({ missingAssets: ['figures/rook.svg'] })
    const response = {
      revisionId: document.revisionId,
      status: 'uploaded',
      version: 3,
      missingAssets: ['figures/rook.svg'],
      assets: [
        {
          logicalName: 'figures/rook.svg',
          sourceKind: 'figure',
          status: 'missing',
          acceptedUploadKinds: ['raster', 'svg'],
          asset: null,
        },
        {
          logicalName: 'tikz/diagram-1',
          sourceKind: 'tikz',
          status: 'attached',
          acceptedUploadKinds: ['tikz'],
          asset: {
            assetId: 'asset-tikz-diagram-1',
            contentSha256: 'a'.repeat(64),
            src: '/staff/api/v1/content/assets/asset-tikz-diagram-1',
            mediaType: 'image/svg+xml',
            width: 640,
            height: 360,
          },
        },
      ],
      requestId: 'asset-contract-test',
    } as const

    expect(staffContentRevisionAssetsSchema.parse(response).missingAssets).toEqual([
      'figures/rook.svg',
    ])
    expect(staffContentAssetResolveSchema.parse({ ...response, reusedCount: 1 }).reusedCount).toBe(
      1,
    )
    expect(() =>
      staffContentRevisionAssetsSchema.parse({ ...response, missingAssets: [] }),
    ).toThrow()
    expect(() =>
      staffContentRevisionAssetsSchema.parse({
        ...response,
        assets: [response.assets[0], response.assets[0]],
        missingAssets: ['figures/rook.svg', 'figures/rook.svg'],
      }),
    ).toThrow()
    expect(() =>
      staffContentRevisionAssetsSchema.parse({
        ...response,
        assets: [
          {
            ...response.assets[0],
            acceptedUploadKinds: ['tikz'],
          },
          response.assets[1],
        ],
      }),
    ).toThrow()
    expect(() =>
      staffContentRevisionAssetsSchema.parse({
        ...response,
        assets: [
          response.assets[0],
          {
            ...response.assets[1],
            asset: {
              ...response.assets[1].asset,
              mediaType: 'image/webp',
            },
          },
        ],
      }),
    ).toThrow()

    expect(
      staffContentAssetUploadSchema.parse({
        revisionId: document.revisionId,
        status: 'uploaded',
        version: 4,
        logicalName: 'figures/rook.svg',
        sourceKind: 'figure',
        asset: {
          assetId: 'asset-rook',
          contentSha256: 'b'.repeat(64),
          src: 'https://assets.example.test/content/rook.webp',
          mediaType: 'image/webp',
          width: 1280,
          height: 720,
        },
        reused: true,
        requestId: 'asset-upload-contract-test',
      }).reused,
    ).toBe(true)
    expect(() =>
      staffContentAssetUploadSchema.parse({
        revisionId: document.revisionId,
        status: 'uploaded',
        version: 4,
        logicalName: 'figures/rook.png',
        sourceKind: 'figure',
        asset: {
          assetId: 'asset-rook-original',
          contentSha256: 'b'.repeat(64),
          src: '/pwa-content-assets/asset-rook-original',
          mediaType: 'image/png',
          width: 1280,
          height: 720,
        },
        reused: false,
        requestId: 'asset-upload-original-test',
      }),
    ).toThrow()
    expect(() =>
      staffContentAssetUploadSchema.parse({
        revisionId: document.revisionId,
        status: 'uploaded',
        version: 4,
        logicalName: 'tikz/diagram-1',
        sourceKind: 'tikz',
        asset: {
          assetId: 'asset-tikz-webp',
          contentSha256: 'c'.repeat(64),
          src: '/pwa-content-assets/asset-tikz-webp',
          mediaType: 'image/webp',
          width: 640,
          height: 360,
        },
        reused: false,
        requestId: 'asset-upload-tikz-webp-test',
      }),
    ).toThrow()
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

  it('validates complete problem matching batches and all historical answer types', () => {
    const review = problemMatchReviewSchema.parse({
      revisionId: document.revisionId,
      groupLessonId: 'group-lesson-41-n',
      version: 1,
      etag: '"review-content-revision-41:v1"',
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
      requestId: 'problem-review-contract-test',
    })

    expect(review.items[0]?.suggestedProblemId).toBe(-41)
    expect(historicalAnswerTypeValues).toHaveLength(23)
    expect(
      historicalAnswerTypeValues.every(
        (answerType) =>
          problemMetadataMutationRequestSchema.safeParse({
            revisionId: document.revisionId,
            rows: [
              {
                problemId: -answerType,
                sourceOrdinal: answerType,
                sourceItem: String(answerType),
                displayNumber: String(answerType),
                title: `Тип ответа ${answerType}`,
                problemType: 1,
                answerType,
                answerValidation: null,
                validationError: null,
                correctAnswer: null,
                correctAnswerChecker: null,
                wrongAnswer: null,
                congratulation: null,
              },
            ],
          }).success,
      ),
    ).toBe(true)
  })

  it('rejects contradictory or duplicate matching decisions before HTTP', () => {
    const row = {
      sourceOrdinal: 1,
      sourceItem: '1',
      decision: 'manual_match',
      problemId: -41,
    } as const

    expect(problemMatchMutationRequestSchema.parse({ matches: [row] })).toEqual({
      matches: [row],
    })
    expect(() =>
      problemMatchMutationRequestSchema.parse({
        matches: [row, { ...row, sourceOrdinal: 2, sourceItem: '2' }],
      }),
    ).toThrow()
    expect(() =>
      problemMatchMutationRequestSchema.parse({
        matches: [{ ...row, decision: 'omit', problemId: -41 }],
      }),
    ).toThrow()
    expect(() =>
      problemMatchMutationRequestSchema.parse({
        matches: [{ ...row, decision: 'insert_new', problemId: -41 }],
      }),
    ).toThrow()
  })

  it('keeps metadata rows type-safe and strips empty optional answer values', () => {
    const grid = problemMetadataGridSchema.parse({
      revisionId: document.revisionId,
      groupLessonId: 'group-lesson-41-n',
      version: 3,
      etag: '"review-content-revision-41:v3"',
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
      requestId: 'metadata-contract-test',
    })

    const { reviewed, ...draftRow } = grid.rows[0]!
    expect(reviewed).toBe(false)
    const normalized = problemMetadataMutationRequestSchema.parse({
      revisionId: document.revisionId,
      rows: [
        {
          ...draftRow,
          answerValidation: '',
          correctAnswerChecker: '',
        },
      ],
    })
    expect(normalized.rows[0]?.answerValidation).toBeNull()
    expect(normalized.rows[0]?.correctAnswerChecker).toBeNull()
    expect(() =>
      problemMetadataMutationRequestSchema.parse({
        revisionId: document.revisionId,
        rows: [
          {
            ...grid.rows[0],
            reviewed: undefined,
            problemType: 2,
            answerType: 2,
          },
        ],
      }),
    ).toThrow()
    expect(() =>
      problemMetadataGridSchema.parse({
        ...grid,
        rows: [grid.rows[0], grid.rows[0]],
      }),
    ).toThrow()
  })
})
