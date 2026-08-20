import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { webAssetUrlSchema, webContentDocumentSchema } from './content'

/**
 * Phase-2 HTTP boundary for LaTeX revisions and published browser content.
 * Keep this wire projection narrower than the compiler AST; see
 * `dev/development-plan/06-phase-2-content.md` and
 * `apps/pwa_api/content_routes.py`.
 */

export const contentMaterialKindSchema = z.enum(['condition', 'hint', 'solution'])
export type ContentMaterialKind = z.infer<typeof contentMaterialKindSchema>

export const businessTimezoneSchema = z
  .string()
  .trim()
  .min(1)
  .max(120)
  .superRefine((timezone, context) => {
    try {
      new Intl.DateTimeFormat('en-US', { timeZone: timezone }).format(0)
    } catch {
      context.addIssue({
        code: 'custom',
        message: 'Expected an IANA business timezone',
      })
    }
  })
export type BusinessTimezone = z.infer<typeof businessTimezoneSchema>

// `datetime-local` deliberately carries no offset. The server combines this
// wall time with its authoritative group-lesson IANA zone and rejects DST
// gaps/folds; the browser must never guess using its own timezone.
export const localPublicationTimeSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
  .superRefine((value, context) => {
    const [datePart, timePart] = value.split('T') as [string, string]
    const [year, month, day] = datePart.split('-').map(Number) as [number, number, number]
    const [hour, minute] = timePart.split(':').map(Number) as [number, number]
    const candidate = new Date(0)
    candidate.setUTCFullYear(year, month - 1, day)
    candidate.setUTCHours(hour, minute, 0, 0)
    if (
      candidate.getUTCFullYear() !== year ||
      candidate.getUTCMonth() !== month - 1 ||
      candidate.getUTCDate() !== day ||
      candidate.getUTCHours() !== hour ||
      candidate.getUTCMinutes() !== minute
    ) {
      context.addIssue({ code: 'custom', message: 'Expected a valid local calendar time' })
    }
  })
export type LocalPublicationTime = z.infer<typeof localPublicationTimeSchema>

export const contentRevisionStatusSchema = z.enum([
  'uploaded',
  'compiling',
  'ready',
  'invalid',
  'superseded',
])
export type ContentRevisionStatus = z.infer<typeof contentRevisionStatusSchema>

export const contentEtagSchema = z
  .string()
  .regex(/^"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?:v[1-9]\d*"$/)
  .brand<'ContentEtag'>()
export type ContentEtag = z.infer<typeof contentEtagSchema>

export const contentIfMatchSchema = z.union([contentEtagSchema, z.literal('"none"')])
export type ContentIfMatch = z.infer<typeof contentIfMatchSchema>

const optionalPublicationPairShape = {
  expectedCurrentPublicationId: publicIdSchema.nullable(),
  expectedCurrentVersion: z.number().int().positive().nullable(),
}

function refinePublicationPair(
  id: string | null,
  version: number | null,
  context: z.RefinementCtx,
  path: string,
): void {
  if ((id === null) !== (version === null)) {
    context.addIssue({
      code: 'custom',
      message: 'Publication ID and version must both be set or both be null',
      path: [path],
    })
  }
}

export const publishContentRequestSchema = z
  .object({
    groupLessonId: publicIdSchema,
    kind: contentMaterialKindSchema,
    revisionId: publicIdSchema,
    mode: z.enum(['publish', 'schedule']),
    scheduledLocalTime: localPublicationTimeSchema.nullable(),
    businessTimezone: businessTimezoneSchema.nullable(),
    ...optionalPublicationPairShape,
    expectedScheduledPublicationId: publicIdSchema.nullable(),
    expectedScheduledVersion: z.number().int().positive().nullable(),
  })
  .strict()
  .superRefine((request, context) => {
    refinePublicationPair(
      request.expectedCurrentPublicationId,
      request.expectedCurrentVersion,
      context,
      'expectedCurrentPublicationId',
    )
    refinePublicationPair(
      request.expectedScheduledPublicationId,
      request.expectedScheduledVersion,
      context,
      'expectedScheduledPublicationId',
    )
    if (
      request.mode === 'publish' &&
      (request.scheduledLocalTime !== null || request.businessTimezone !== null)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Immediate publication cannot carry schedule fields',
        path: ['scheduledLocalTime'],
      })
    }
    if (request.mode === 'schedule') {
      if (request.scheduledLocalTime === null) {
        context.addIssue({
          code: 'custom',
          message: 'Scheduled publication requires scheduledLocalTime',
          path: ['scheduledLocalTime'],
        })
      }
      if (request.businessTimezone === null) {
        context.addIssue({
          code: 'custom',
          message: 'Scheduled publication requires businessTimezone',
          path: ['businessTimezone'],
        })
      }
      if (
        request.expectedCurrentPublicationId !== request.expectedScheduledPublicationId ||
        request.expectedCurrentVersion !== request.expectedScheduledVersion
      ) {
        context.addIssue({
          code: 'custom',
          message: 'Schedule mode must describe the same primary and scheduled slot',
          path: ['expectedScheduledPublicationId'],
        })
      }
    }
  })
export type PublishContentRequest = z.infer<typeof publishContentRequestSchema>

export const rollbackContentRequestSchema = z
  .object({
    revisionId: publicIdSchema,
    expectedScheduledPublicationId: publicIdSchema.nullable(),
    expectedScheduledVersion: z.number().int().positive().nullable(),
  })
  .strict()
  .superRefine((request, context) => {
    refinePublicationPair(
      request.expectedScheduledPublicationId,
      request.expectedScheduledVersion,
      context,
      'expectedScheduledPublicationId',
    )
  })
export type RollbackContentRequest = z.infer<typeof rollbackContentRequestSchema>

export const emptyContentMutationRequestSchema = z.object({}).strict()

export const contentPublicationStateSchema = z.enum([
  'scheduled',
  'published',
  'hidden',
  'superseded',
])
export type ContentPublicationState = z.infer<typeof contentPublicationStateSchema>

const sourcePositionSchema = z
  .object({
    offset: z.number().int().nonnegative(),
    line: z.number().int().positive(),
    column: z.number().int().positive(),
  })
  .strict()

export const contentDiagnosticSchema = z
  .object({
    code: z.string().trim().min(1).max(160),
    severity: z.enum(['info', 'warning', 'error']),
    message: z.string().trim().min(1).max(8_192),
    span: z
      .object({
        source_name: z.string().trim().min(1).max(240),
        start: sourcePositionSchema,
        end: sourcePositionSchema,
      })
      .strict(),
    recovery: z.string().trim().min(1).max(8_192).nullable(),
  })
  .strict()
export type ContentDiagnostic = z.infer<typeof contentDiagnosticSchema>

export const staffContentRevisionSchema = z
  .object({
    revisionId: publicIdSchema,
    sourceId: publicIdSchema,
    groupLessonId: publicIdSchema,
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    kind: contentMaterialKindSchema,
    logicalFilename: z.string().trim().min(1).max(240),
    revisionNumber: z.number().int().positive(),
    uploadedAt: z.iso.datetime(),
    status: contentRevisionStatusSchema,
    version: z.number().int().positive(),
    compileLeaseExpiresAt: z.iso.datetime().nullable(),
    compileAttempt: z.number().int().nonnegative(),
    sourceSha256: z.string().regex(/^[0-9a-f]{64}$/),
    parserVersion: z.string().trim().min(1).max(200),
    diagnostics: z.array(contentDiagnosticSchema).max(10_000),
    missingAssets: z.array(z.string().trim().min(1).max(2_000)).max(10_000),
    requestId: z.string().trim().min(1).max(200).optional(),
  })
  .strict()
export type StaffContentRevision = z.infer<typeof staffContentRevisionSchema>

export const contentAssetsMissingDetailsSchema = z
  .object({
    missingAssets: z.array(z.string().trim().min(1).max(2_000)).min(1).max(10_000),
  })
  .strict()
export type ContentAssetsMissingDetails = z.infer<typeof contentAssetsMissingDetailsSchema>

export const contentAssetUploadKindSchema = z.enum(['raster', 'svg', 'tikz'])
export type ContentAssetUploadKind = z.infer<typeof contentAssetUploadKindSchema>

export const contentAssetSourceKindSchema = z.enum(['figure', 'tikz'])
export type ContentAssetSourceKind = z.infer<typeof contentAssetSourceKindSchema>

export const contentRevisionAssetSchema = z
  .object({
    assetId: publicIdSchema,
    contentSha256: z.string().regex(/^[0-9a-f]{64}$/),
    src: webAssetUrlSchema,
    mediaType: z.enum(['image/svg+xml', 'image/webp']),
    width: z.number().int().positive().max(20_000),
    height: z.number().int().positive().max(20_000),
  })
  .strict()
export type ContentRevisionAsset = z.infer<typeof contentRevisionAssetSchema>

export const contentRevisionAssetSlotSchema = z
  .object({
    logicalName: z.string().trim().min(1).max(2_000),
    sourceKind: contentAssetSourceKindSchema,
    status: z.enum(['missing', 'attached']),
    acceptedUploadKinds: z.array(contentAssetUploadKindSchema).min(1).max(3),
    asset: contentRevisionAssetSchema.nullable(),
  })
  .strict()
  .superRefine((slot, context) => {
    if (new Set(slot.acceptedUploadKinds).size !== slot.acceptedUploadKinds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Accepted upload kinds must be unique',
        path: ['acceptedUploadKinds'],
      })
    }
    if (
      slot.sourceKind === 'tikz' &&
      (slot.acceptedUploadKinds.length !== 1 || slot.acceptedUploadKinds[0] !== 'tikz')
    ) {
      context.addIssue({
        code: 'custom',
        message: 'TikZ slots accept only server-side TikZ generation',
        path: ['acceptedUploadKinds'],
      })
    }
    if (
      slot.sourceKind === 'figure' &&
      (slot.acceptedUploadKinds.length !== 2 ||
        !slot.acceptedUploadKinds.includes('raster') ||
        !slot.acceptedUploadKinds.includes('svg'))
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Figure slots accept exactly raster and SVG uploads',
        path: ['acceptedUploadKinds'],
      })
    }
    if (
      slot.sourceKind === 'tikz' &&
      slot.asset !== null &&
      slot.asset.mediaType !== 'image/svg+xml'
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Attached TikZ derivatives must be SVG',
        path: ['asset', 'mediaType'],
      })
    }
    if ((slot.status === 'missing') !== (slot.asset === null)) {
      context.addIssue({
        code: 'custom',
        message: 'Missing asset slots must have null asset and attached slots must carry an asset',
        path: ['asset'],
      })
    }
  })
export type ContentRevisionAssetSlot = z.infer<typeof contentRevisionAssetSlotSchema>

export const staffContentRevisionAssetsSchema = z
  .object({
    revisionId: publicIdSchema,
    status: contentRevisionStatusSchema,
    version: z.number().int().positive(),
    missingAssets: z.array(z.string().trim().min(1).max(2_000)).max(10_000),
    assets: z.array(contentRevisionAssetSlotSchema).max(10_000),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((response, context) => {
    const logicalNames = response.assets.map((asset) => asset.logicalName)
    if (new Set(logicalNames).size !== logicalNames.length) {
      context.addIssue({
        code: 'custom',
        message: 'Revision asset logical names must be unique',
        path: ['assets'],
      })
    }
    const missingFromSlots = response.assets
      .filter((asset) => asset.status === 'missing')
      .map((asset) => asset.logicalName)
      .sort()
    const declaredMissing = [...response.missingAssets].sort()
    if (
      missingFromSlots.length !== declaredMissing.length ||
      missingFromSlots.some((logicalName, index) => logicalName !== declaredMissing[index])
    ) {
      context.addIssue({
        code: 'custom',
        message: 'missingAssets must exactly match missing asset slots',
        path: ['missingAssets'],
      })
    }
  })
export type StaffContentRevisionAssets = z.infer<typeof staffContentRevisionAssetsSchema>

export const staffContentAssetResolveSchema = staffContentRevisionAssetsSchema.safeExtend({
  reusedCount: z.number().int().nonnegative().max(10_000),
})
export type StaffContentAssetResolve = z.infer<typeof staffContentAssetResolveSchema>

export const staffContentAssetUploadSchema = z
  .object({
    revisionId: publicIdSchema,
    status: contentRevisionStatusSchema,
    version: z.number().int().positive(),
    logicalName: z.string().trim().min(1).max(2_000),
    sourceKind: contentAssetSourceKindSchema,
    asset: contentRevisionAssetSchema,
    reused: z.boolean(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((response, context) => {
    if (response.sourceKind === 'tikz' && response.asset.mediaType !== 'image/svg+xml') {
      context.addIssue({
        code: 'custom',
        message: 'Uploaded TikZ derivatives must be SVG',
        path: ['asset', 'mediaType'],
      })
    }
  })
export type StaffContentAssetUpload = z.infer<typeof staffContentAssetUploadSchema>

export const contentUploadTargetSchema = z
  .object({
    groupLessonId: publicIdSchema,
    groupId: publicIdSchema,
    groupName: z.string().trim().min(1).max(200),
    groupShortCode: z.string().trim().min(1).max(40),
    colorKey: z.string().trim().min(1).max(80).nullable(),
    status: z.enum(['draft', 'active', 'archived']),
  })
  .strict()
export type ContentUploadTarget = z.infer<typeof contentUploadTargetSchema>

export const staffContentUploadTargetsSchema = z
  .object({
    courseLessonId: publicIdSchema,
    courseId: publicIdSchema,
    courseName: z.string().trim().min(1).max(200),
    lessonNumber: z.number().int().nonnegative(),
    targets: z.array(contentUploadTargetSchema).min(1).max(100),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((response, context) => {
    for (const field of ['groupLessonId', 'groupId'] as const) {
      const values = response.targets.map((target) => target[field])
      if (new Set(values).size !== values.length) {
        context.addIssue({
          code: 'custom',
          message: `Bulk upload targets must have unique ${field}`,
          path: ['targets'],
        })
      }
    }
  })
export type StaffContentUploadTargets = z.infer<typeof staffContentUploadTargetsSchema>

export const staffWebContentPreviewSchema = z
  .object({
    revisionId: publicIdSchema,
    kind: z.literal('web'),
    document: webContentDocumentSchema,
  })
  .strict()
  .superRefine((preview, context) => {
    if (preview.document.revisionId !== preview.revisionId) {
      context.addIssue({
        code: 'custom',
        message: 'Preview revision must match the document revision',
        path: ['document', 'revisionId'],
      })
    }
  })

export const staffTelegramContentPreviewSchema = z
  .object({
    revisionId: publicIdSchema,
    kind: z.literal('telegram'),
    // Python and Telegram count Unicode code points, while JavaScript's
    // `length` counts UTF-16 code units. The outer cap bounds parsing work;
    // this refinement preserves a valid 32,768-emoji payload.
    html: z
      .string()
      .max(65_536)
      .superRefine((html, context) => {
        if (Array.from(html).length > 32_768) {
          context.addIssue({
            code: 'too_big',
            maximum: 32_768,
            origin: 'string',
            inclusive: true,
            message: 'Telegram Rich HTML exceeds 32,768 Unicode characters',
          })
        }
      }),
  })
  .strict()

export const staffPdfContentPreviewSchema = z
  .object({
    revisionId: publicIdSchema,
    kind: z.literal('pdf'),
    src: z
      .string()
      .max(400)
      .regex(/^\/staff\/api\/v1\/content\/revisions\/[A-Za-z0-9._:-]+\/pdf$/),
    contentSha256: z.string().regex(/^[0-9a-f]{64}$/),
    byteSize: z
      .number()
      .int()
      .positive()
      .max(64 * 1024 * 1024),
    rendererVersion: z.string().trim().min(1).max(200),
  })
  .strict()
export type StaffPdfContentPreview = z.infer<typeof staffPdfContentPreviewSchema>

export const staffContentPreviewSchema = z.union([
  staffWebContentPreviewSchema,
  staffTelegramContentPreviewSchema,
  staffPdfContentPreviewSchema,
])
export type StaffContentPreview = z.infer<typeof staffContentPreviewSchema>

export const contentPublicationSchema = z
  .object({
    publicationId: publicIdSchema,
    groupLessonId: publicIdSchema,
    revisionId: publicIdSchema,
    kind: contentMaterialKindSchema,
    state: contentPublicationStateSchema,
    version: z.number().int().positive(),
    scheduledAt: z.iso.datetime().nullable(),
    publishedAt: z.iso.datetime().nullable(),
    hiddenAt: z.iso.datetime().nullable(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
export type ContentPublication = z.infer<typeof contentPublicationSchema>

export const contentPublicationHistoryItemSchema = z
  .object({
    publicationId: publicIdSchema,
    revisionId: publicIdSchema,
    kind: contentMaterialKindSchema,
    state: contentPublicationStateSchema,
    version: z.number().int().positive(),
    scheduledAt: z.iso.datetime().nullable(),
    publishedAt: z.iso.datetime().nullable(),
    hiddenAt: z.iso.datetime().nullable(),
    etag: contentEtagSchema,
  })
  .strict()
export type ContentPublicationHistoryItem = z.infer<typeof contentPublicationHistoryItemSchema>

export const staffContentHistoryRevisionSchema = staffContentRevisionSchema
  .extend({ etag: contentEtagSchema })
  .strict()

export const staffContentMaterialHistorySchema = z
  .object({
    kind: contentMaterialKindSchema,
    revisions: z.array(staffContentHistoryRevisionSchema).max(10_000),
    currentPublished: contentPublicationHistoryItemSchema.nullable(),
    currentScheduled: contentPublicationHistoryItemSchema.nullable(),
    publicationHistory: z.array(contentPublicationHistoryItemSchema).max(10_000),
  })
  .strict()
  .superRefine((material, context) => {
    if (material.currentPublished && material.currentPublished.state !== 'published') {
      context.addIssue({
        code: 'custom',
        message: 'Current published slot must contain a published row',
        path: ['currentPublished', 'state'],
      })
    }
    if (material.currentScheduled && material.currentScheduled.state !== 'scheduled') {
      context.addIssue({
        code: 'custom',
        message: 'Current scheduled slot must contain a scheduled row',
        path: ['currentScheduled', 'state'],
      })
    }
    const publications = [
      material.currentPublished,
      material.currentScheduled,
      ...material.publicationHistory,
    ].filter((publication) => publication !== null)
    publications.forEach((publication) => {
      if (publication.kind !== material.kind) {
        context.addIssue({
          code: 'custom',
          message: 'Publication history kind must match its material slot',
          path: ['publicationHistory'],
        })
      }
    })
    material.revisions.forEach((revision, index) => {
      if (revision.kind !== material.kind) {
        context.addIssue({
          code: 'custom',
          message: 'Revision history kind must match its material slot',
          path: ['revisions', index, 'kind'],
        })
      }
    })
  })
export type StaffContentMaterialHistory = z.infer<typeof staffContentMaterialHistorySchema>

export const staffContentHistorySchema = z
  .object({
    groupLessonId: publicIdSchema,
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    businessTimezone: businessTimezoneSchema,
    materials: z.array(staffContentMaterialHistorySchema).length(3),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((history, context) => {
    const kinds = new Set(history.materials.map((material) => material.kind))
    if (kinds.size !== 3) {
      context.addIssue({
        code: 'custom',
        message: 'Content history must contain one slot for every material kind',
        path: ['materials'],
      })
    }
  })
export type StaffContentHistory = z.infer<typeof staffContentHistorySchema>

export const staffLessonWindowSchema = z
  .object({
    lessonWindowId: publicIdSchema,
    groupLessonId: publicIdSchema,
    opensAt: z.iso.datetime({ offset: true }).nullable(),
    submissionClosesAt: z.iso.datetime({ offset: true }),
    hintScheduledAt: z.iso.datetime({ offset: true }).nullable(),
    solutionScheduledAt: z.iso.datetime({ offset: true }).nullable(),
    businessTimezone: businessTimezoneSchema,
    source: z.enum(['native', 'legacy_schedule', 'manual_backfill']),
    version: z.number().int().positive(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
export type StaffLessonWindow = z.infer<typeof staffLessonWindowSchema>

export const updateStaffLessonWindowScheduleSchema = z
  .object({
    opensLocalTime: localPublicationTimeSchema.nullable(),
    hintScheduledLocalTime: localPublicationTimeSchema.nullable(),
    solutionScheduledLocalTime: localPublicationTimeSchema.nullable(),
    businessTimezone: businessTimezoneSchema,
  })
  .strict()
export type UpdateStaffLessonWindowSchedule = z.infer<typeof updateStaffLessonWindowScheduleSchema>

export const updateStaffSubmissionCutoffSchema = z
  .object({
    submissionClosesLocalTime: localPublicationTimeSchema,
    businessTimezone: businessTimezoneSchema,
    confirmChange: z.literal(true),
  })
  .strict()
export type UpdateStaffSubmissionCutoff = z.infer<typeof updateStaffSubmissionCutoffSchema>

// `problemId` is deliberately the only legacy integer on this Staff-only
// reconciliation boundary. Phase 3 replaces it with an opaque public ID before
// task data reaches Student/Family; see Phase 2 MATCH-03 and METADATA-01.
export const legacyProblemIdSchema = z
  .number()
  .int()
  .refine(Number.isSafeInteger, 'Expected a safe integer problem ID')
  .refine((value) => value !== 0, 'Problem ID cannot be zero')

export const problemTypeSchema = z
  .number()
  .int()
  .refine((value) => value >= 1 && value <= 4, 'Unknown problem type')
export type ProblemType = z.infer<typeof problemTypeSchema>

export const historicalAnswerTypeValues = [
  1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 98, 99,
] as const
export const answerTypeSchema = z
  .number()
  .int()
  .refine(
    (value): value is (typeof historicalAnswerTypeValues)[number] =>
      (historicalAnswerTypeValues as readonly number[]).includes(value),
    'Unknown historical answer type',
  )
export type AnswerType = z.infer<typeof answerTypeSchema>

const sourceItemSchema = z.string().trim().min(1).max(80)
const displayNumberSchema = z.string().trim().min(1).max(80)
const problemTitleSchema = z.string().trim().min(1).max(500)
const nullableAnswerTextSchema = z
  .string()
  .trim()
  .max(4_000)
  .nullable()
  .transform((value) => (value === '' ? null : value))
const nullableCheckerSchema = z
  .string()
  .trim()
  .max(65_536)
  .nullable()
  .transform((value) => (value === '' ? null : value))

export const problemMatchDecisionSchema = z.enum([
  'auto_position',
  'manual_match',
  'insert_new',
  'omit',
])
export type ProblemMatchDecision = z.infer<typeof problemMatchDecisionSchema>

export const legacyProblemCandidateSchema = z
  .object({
    problemId: legacyProblemIdSchema,
    problemNumber: z.number().int().nonnegative(),
    // Historical rows can contain blank item/title values. They remain visible
    // candidates, but the reviewed metadata request below requires both fields.
    item: z.string().max(80),
    title: z.string().max(500),
    problemType: problemTypeSchema,
    answerType: answerTypeSchema.nullable(),
    answerValidation: z.string().max(4_000).nullable(),
    validationError: z.string().max(4_000).nullable(),
    correctAnswer: z.string().max(4_000).nullable(),
    correctAnswerChecker: z.string().max(65_536).nullable(),
    wrongAnswer: z.string().max(4_000).nullable(),
    congratulation: z.string().max(4_000).nullable(),
  })
  .strict()
export type LegacyProblemCandidate = z.infer<typeof legacyProblemCandidateSchema>

const resolvedProblemMatchSchema = z
  .object({
    decision: problemMatchDecisionSchema,
    problemId: legacyProblemIdSchema.nullable(),
  })
  .strict()
  .superRefine((match, context) => {
    if (match.decision === 'omit' && match.problemId !== null) {
      context.addIssue({
        code: 'custom',
        message: 'Omitted problems cannot carry a problem ID',
        path: ['problemId'],
      })
    }
    if (match.decision !== 'omit' && match.problemId === null) {
      context.addIssue({
        code: 'custom',
        message: 'Resolved problems require a problem ID',
        path: ['problemId'],
      })
    }
  })

export const problemMatchReviewItemSchema = z
  .object({
    sourceOrdinal: z.number().int().nonnegative(),
    sourceItem: sourceItemSchema,
    displayNumber: displayNumberSchema,
    sourceTitle: z.string().trim().min(1).max(500).nullable(),
    suggestedProblemId: legacyProblemIdSchema.nullable(),
    match: resolvedProblemMatchSchema.nullable(),
  })
  .strict()
export type ProblemMatchReviewItem = z.infer<typeof problemMatchReviewItemSchema>

export const problemMatchReviewSchema = z
  .object({
    revisionId: publicIdSchema,
    groupLessonId: publicIdSchema,
    version: z.number().int().positive(),
    etag: contentEtagSchema,
    items: z.array(problemMatchReviewItemSchema).max(2_000),
    candidates: z.array(legacyProblemCandidateSchema).max(5_000),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((review, context) => {
    const identities = review.items.map((item) => `${item.sourceOrdinal}\u0000${item.sourceItem}`)
    if (new Set(identities).size !== identities.length) {
      context.addIssue({ code: 'custom', message: 'Canonical problem identities must be unique' })
    }
    const candidateIds = review.candidates.map((candidate) => candidate.problemId)
    if (new Set(candidateIds).size !== candidateIds.length) {
      context.addIssue({ code: 'custom', message: 'Problem candidates must be unique' })
    }
    const candidateIdSet = new Set(candidateIds)
    review.items.forEach((item, index) => {
      if (item.suggestedProblemId !== null && !candidateIdSet.has(item.suggestedProblemId)) {
        context.addIssue({
          code: 'custom',
          message: 'Suggested problem must be present in candidates',
          path: ['items', index, 'suggestedProblemId'],
        })
      }
    })
  })
export type ProblemMatchReview = z.infer<typeof problemMatchReviewSchema>

export const problemMatchMutationRowSchema = z
  .object({
    sourceOrdinal: z.number().int().nonnegative(),
    sourceItem: sourceItemSchema,
    decision: problemMatchDecisionSchema,
    problemId: legacyProblemIdSchema.nullable(),
  })
  .strict()
  .superRefine((row, context) => {
    const requiresProblem = row.decision === 'auto_position' || row.decision === 'manual_match'
    if (requiresProblem !== (row.problemId !== null)) {
      context.addIssue({
        code: 'custom',
        message: requiresProblem
          ? 'Existing-problem matches require a problem ID'
          : 'New and omitted problems cannot carry a problem ID',
        path: ['problemId'],
      })
    }
  })
export type ProblemMatchMutationRow = z.infer<typeof problemMatchMutationRowSchema>

export const problemMatchMutationRequestSchema = z
  .object({ matches: z.array(problemMatchMutationRowSchema).max(2_000) })
  .strict()
  .superRefine((request, context) => {
    const identities = request.matches.map(
      (item) => `${item.sourceOrdinal}\u0000${item.sourceItem}`,
    )
    if (new Set(identities).size !== identities.length) {
      context.addIssue({ code: 'custom', message: 'Canonical problem identities must be unique' })
    }
    const problemIds = request.matches.flatMap((item) =>
      item.problemId === null ? [] : [item.problemId],
    )
    if (new Set(problemIds).size !== problemIds.length) {
      context.addIssue({ code: 'custom', message: 'A problem may be matched only once' })
    }
  })
export type ProblemMatchMutationRequest = z.infer<typeof problemMatchMutationRequestSchema>

const problemMetadataMutationShape = {
  problemId: legacyProblemIdSchema,
  sourceOrdinal: z.number().int().nonnegative(),
  sourceItem: sourceItemSchema,
  displayNumber: displayNumberSchema,
  title: problemTitleSchema,
  problemType: problemTypeSchema,
  answerType: answerTypeSchema.nullable(),
  answerValidation: nullableAnswerTextSchema,
  validationError: nullableAnswerTextSchema,
  correctAnswer: nullableAnswerTextSchema,
  correctAnswerChecker: nullableCheckerSchema,
  wrongAnswer: nullableAnswerTextSchema,
  congratulation: nullableAnswerTextSchema,
}

function validateProblemMetadata(
  row: {
    problemType: number
    answerType: number | null
    answerValidation: string | null
    validationError: string | null
    correctAnswer: string | null
    correctAnswerChecker: string | null
    wrongAnswer: string | null
    congratulation: string | null
  },
  context: z.RefinementCtx,
): void {
  if (row.problemType === 1 && row.answerType === null) {
    context.addIssue({
      code: 'custom',
      message: 'Test problems require an answer type',
      path: ['answerType'],
    })
  }
  if (row.problemType !== 1) {
    const answerFields = [
      'answerValidation',
      'validationError',
      'correctAnswer',
      'correctAnswerChecker',
      'wrongAnswer',
      'congratulation',
    ] as const
    if (row.answerType !== null) {
      context.addIssue({
        code: 'custom',
        message: 'Only test problems can have an answer type',
        path: ['answerType'],
      })
    }
    answerFields.forEach((field) => {
      if (row[field] !== null) {
        context.addIssue({
          code: 'custom',
          message: 'Non-test problems cannot retain test answer configuration',
          path: [field],
        })
      }
    })
  }
}

export const problemMetadataMutationRowSchema = z
  .object(problemMetadataMutationShape)
  .strict()
  .superRefine(validateProblemMetadata)
export type ProblemMetadataMutationRow = z.infer<typeof problemMetadataMutationRowSchema>

export const problemMetadataGridRowSchema = z
  .object({
    ...problemMetadataMutationShape,
    title: z.string().max(500),
    answerValidation: z.string().max(4_000).nullable(),
    validationError: z.string().max(4_000).nullable(),
    correctAnswer: z.string().max(4_000).nullable(),
    correctAnswerChecker: z.string().max(65_536).nullable(),
    wrongAnswer: z.string().max(4_000).nullable(),
    congratulation: z.string().max(4_000).nullable(),
    reviewed: z.boolean(),
  })
  .strict()
  .superRefine((row, context) => {
    if (row.reviewed) {
      if (!row.title.trim()) {
        context.addIssue({
          code: 'custom',
          message: 'Reviewed problems require a title',
          path: ['title'],
        })
      }
      validateProblemMetadata(row, context)
    }
  })
export type ProblemMetadataGridRow = z.infer<typeof problemMetadataGridRowSchema>

export const problemMetadataGridSchema = z
  .object({
    revisionId: publicIdSchema,
    groupLessonId: publicIdSchema,
    version: z.number().int().positive(),
    etag: contentEtagSchema,
    rows: z.array(problemMetadataGridRowSchema).max(2_000),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((grid, context) => {
    const identities = grid.rows.map((row) => `${row.sourceOrdinal}\u0000${row.sourceItem}`)
    const problemIds = grid.rows.map((row) => row.problemId)
    if (new Set(identities).size !== identities.length) {
      context.addIssue({ code: 'custom', message: 'Metadata identities must be unique' })
    }
    if (new Set(problemIds).size !== problemIds.length) {
      context.addIssue({ code: 'custom', message: 'Metadata problem IDs must be unique' })
    }
  })
export type ProblemMetadataGrid = z.infer<typeof problemMetadataGridSchema>

export const problemMetadataMutationRequestSchema = z
  .object({
    revisionId: publicIdSchema,
    rows: z.array(problemMetadataMutationRowSchema).max(2_000),
  })
  .strict()
  .superRefine((request, context) => {
    const identities = request.rows.map((row) => `${row.sourceOrdinal}\u0000${row.sourceItem}`)
    const problemIds = request.rows.map((row) => row.problemId)
    if (new Set(identities).size !== identities.length) {
      context.addIssue({ code: 'custom', message: 'Metadata identities must be unique' })
    }
    if (new Set(problemIds).size !== problemIds.length) {
      context.addIssue({ code: 'custom', message: 'Metadata problem IDs must be unique' })
    }
  })
export type ProblemMetadataMutationRequest = z.infer<typeof problemMetadataMutationRequestSchema>

export const contentPublicationCancellationSchema = contentPublicationSchema
  .extend({ action: z.literal('cancelled'), state: z.literal('superseded') })
  .strict()
export type ContentPublicationCancellation = z.infer<typeof contentPublicationCancellationSchema>

export const contentPublicationHidingSchema = contentPublicationSchema
  .extend({ action: z.literal('hidden'), state: z.literal('hidden') })
  .strict()
export type ContentPublicationHiding = z.infer<typeof contentPublicationHidingSchema>

export const publishedContentSchema = z
  .object({
    groupLessonId: publicIdSchema,
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    kind: contentMaterialKindSchema,
    publicationId: publicIdSchema,
    publicationVersion: z.number().int().positive(),
    publishedAt: z.iso.datetime(),
    revisionId: publicIdSchema,
    document: webContentDocumentSchema,
  })
  .strict()
  .superRefine((published, context) => {
    if (published.document.revisionId !== published.revisionId) {
      context.addIssue({
        code: 'custom',
        message: 'Published revision must match the document revision',
        path: ['document', 'revisionId'],
      })
    }
    if (published.document.materialKind !== published.kind) {
      context.addIssue({
        code: 'custom',
        message: 'Published material kind must match the document kind',
        path: ['document', 'materialKind'],
      })
    }
  })
export type PublishedContent = z.infer<typeof publishedContentSchema>

export const studentRevealKindSchema = z.enum(['hint', 'solution'])
export type StudentRevealKind = z.infer<typeof studentRevealKindSchema>

export const studentProblemRevealSchema = z
  .object({
    groupLessonId: publicIdSchema,
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    kind: studentRevealKindSchema,
    publicationId: publicIdSchema,
    publicationVersion: z.number().int().positive(),
    publishedAt: z.iso.datetime(),
    revisionId: publicIdSchema,
    problemId: publicIdSchema,
    sourceOrdinal: z.number().int().positive(),
    revealedAt: z.iso.datetime(),
    firstReveal: z.boolean(),
    document: webContentDocumentSchema,
  })
  .strict()
  .superRefine((revealed, context) => {
    if (revealed.document.revisionId !== revealed.revisionId) {
      context.addIssue({
        code: 'custom',
        message: 'Revealed revision must match the document revision',
        path: ['document', 'revisionId'],
      })
    }
    if (revealed.document.materialKind !== revealed.kind) {
      context.addIssue({
        code: 'custom',
        message: 'Revealed material kind must match the document kind',
        path: ['document', 'materialKind'],
      })
    }
    if (
      revealed.document.introduction.length !== 0 ||
      revealed.document.problems.length !== 1 ||
      revealed.document.problems[0]?.ordinal !== revealed.sourceOrdinal
    ) {
      context.addIssue({
        code: 'custom',
        message: 'A reveal must contain exactly its selected problem',
        path: ['document', 'problems'],
      })
    }
  })
export type StudentProblemReveal = z.infer<typeof studentProblemRevealSchema>

export const contentQueryKeys = {
  published: (
    principal: PrincipalQueryScope,
    groupLessonId: string,
    kind: ContentMaterialKind,
    studentPublicId?: string,
  ) =>
    [
      ...principalQueryKey(principal),
      'content',
      'published',
      groupLessonId,
      kind,
      studentPublicId ?? 'self',
    ] as const,
  diagnostics: (revisionId: string) => ['content', 'diagnostics', revisionId] as const,
  assets: (revisionId: string) => ['content', 'assets', revisionId] as const,
  problemMatches: (revisionId: string) => ['content', 'problem-matches', revisionId] as const,
  metadataGrid: (groupLessonId: string, revisionId: string) =>
    ['content', 'metadata-grid', groupLessonId, revisionId] as const,
  history: (groupLessonId: string) => ['content', 'history', groupLessonId] as const,
  lessonWindow: (groupLessonId: string) => ['content', 'lesson-window', groupLessonId] as const,
  uploadTargets: (groupLessonId: string) => ['content', 'upload-targets', groupLessonId] as const,
  preview: (revisionId: string, kind: 'web' | 'telegram' | 'pdf') =>
    ['content', 'preview', revisionId, kind] as const,
} as const
