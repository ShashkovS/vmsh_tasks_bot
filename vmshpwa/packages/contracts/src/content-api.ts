import { z } from 'zod'

import { publicIdSchema } from './auth'
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

export const staffContentPreviewSchema = z.union([
  staffWebContentPreviewSchema,
  staffTelegramContentPreviewSchema,
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

export const contentQueryKeys = {
  published: (
    audience: 'student' | 'family',
    groupLessonId: string,
    kind: ContentMaterialKind,
    studentPublicId?: string,
  ) => ['content', 'published', audience, groupLessonId, kind, studentPublicId ?? 'self'] as const,
  diagnostics: (revisionId: string) => ['content', 'diagnostics', revisionId] as const,
  assets: (revisionId: string) => ['content', 'assets', revisionId] as const,
  history: (groupLessonId: string) => ['content', 'history', groupLessonId] as const,
  preview: (revisionId: string, kind: 'web' | 'telegram') =>
    ['content', 'preview', revisionId, kind] as const,
} as const
