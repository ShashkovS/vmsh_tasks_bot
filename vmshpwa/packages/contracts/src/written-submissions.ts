import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

/** Phase-5 written-thread wire boundary; see development-plan Phase 5. */
export const WRITTEN_SUBMISSION_CONTRACT_VERSION = 1 as const
const contractVersionSchema = z.literal(WRITTEN_SUBMISSION_CONTRACT_VERSION)
const utcClientTimeSchema = z.iso
  .datetime()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/)

export const writtenProblemRevisionSchema = z
  .object({
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
  })
  .strict()
export type WrittenProblemRevision = z.infer<typeof writtenProblemRevisionSchema>

export const writtenAttachmentSchema = z
  .object({
    attachmentId: publicIdSchema,
    ordinal: z.number().int().nonnegative(),
    uploadStatus: z.enum(['pending', 'stored', 'failed', 'locked']),
    mediaId: publicIdSchema,
    publicUrl: z.url().nullable(),
    mediaPath: z
      .string()
      .regex(
        /^\/student\/api\/v1\/thread-entries\/[a-z0-9][a-z0-9._:-]*\/attachments\/[a-z0-9][a-z0-9._:-]*\/media$/,
      ),
    mediaType: z.literal('image/webp'),
    width: z.number().int().min(1).max(1920),
    height: z.number().int().min(1).max(1920),
  })
  .strict()
export type WrittenAttachment = z.infer<typeof writtenAttachmentSchema>

export const writtenEntrySchema = z
  .object({
    entryId: publicIdSchema,
    authorKind: z.enum(['student', 'teacher', 'admin', 'ai', 'system']),
    entryKind: z.enum(['text', 'submission', 'teacher_comment', 'ai_comment', 'system_event']),
    state: z.enum(['draft', 'uploading', 'submitted', 'deleted', 'locked']),
    text: z.string().max(100_000).nullable(),
    problemRevision: writtenProblemRevisionSchema.nullable(),
    version: z.number().int().positive(),
    clientCreatedAt: z.iso.datetime().nullable(),
    serverReceivedAt: z.iso.datetime(),
    attachments: z.array(writtenAttachmentSchema).max(10),
  })
  .strict()
  .superRefine((entry, context) => {
    if (entry.authorKind === 'student' && entry.problemRevision === null) {
      context.addIssue({
        code: 'custom',
        message: 'Student material must keep exact problem-revision provenance',
        path: ['problemRevision'],
      })
    }
    const ordinals = entry.attachments.map((attachment) => attachment.ordinal)
    if (new Set(ordinals).size !== ordinals.length) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment ordinals must be unique',
        path: ['attachments'],
      })
    }
    if (
      ['submitted', 'locked'].includes(entry.state) &&
      !entry.text?.trim() &&
      entry.attachments.length === 0
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Submitted material must contain text or an attachment',
        path: ['state'],
      })
    }
  })
export type WrittenEntry = z.infer<typeof writtenEntrySchema>

export const writtenThreadSchema = z
  .object({
    threadId: publicIdSchema,
    problemId: publicIdSchema,
    status: z.enum(['open', 'awaiting_review', 'needs_work', 'accepted', 'closed']),
    conditionRevisionId: publicIdSchema,
    version: z.number().int().positive(),
    latestEntryAt: z.iso.datetime(),
    entries: z.array(writtenEntrySchema),
  })
  .strict()
  .superRefine((thread, context) => {
    let previous: string | null = null
    const seen = new Set<string>()
    thread.entries.forEach((entry, index) => {
      if (seen.has(entry.entryId)) {
        context.addIssue({
          code: 'custom',
          message: 'Thread entry IDs must be unique',
          path: ['entries', index, 'entryId'],
        })
      }
      if (previous !== null && entry.serverReceivedAt < previous) {
        context.addIssue({
          code: 'custom',
          message: 'Thread entries must use chronological order',
          path: ['entries', index, 'serverReceivedAt'],
        })
      }
      seen.add(entry.entryId)
      previous = entry.serverReceivedAt
    })
  })
export type WrittenThread = z.infer<typeof writtenThreadSchema>

export const createWrittenEntryRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    problemRevision: writtenProblemRevisionSchema,
    text: z.string().max(100_000).nullable(),
    clientCreatedAt: utcClientTimeSchema,
  })
  .strict()
export type CreateWrittenEntryRequest = z.infer<typeof createWrittenEntryRequestSchema>

const writtenEntryMutationShape = {
  schemaVersion: contractVersionSchema,
  threadId: publicIdSchema,
  problemId: publicIdSchema,
  threadStatus: z.enum(['open', 'awaiting_review', 'needs_work', 'accepted', 'closed']),
  threadVersion: z.number().int().positive(),
  entry: writtenEntrySchema,
  requestId: z.string().trim().min(1).max(200),
}

export const createWrittenEntryResponseSchema = z
  .object(writtenEntryMutationShape)
  .strict()
  .superRefine((response, context) => {
    if (
      response.entry.authorKind !== 'student' ||
      response.entry.entryKind !== 'submission' ||
      response.entry.state !== 'draft'
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Create response must contain the new Student draft',
        path: ['entry'],
      })
    }
  })
export type CreateWrittenEntryResponse = z.infer<typeof createWrittenEntryResponseSchema>

/** Typed text fields used to build the multipart attachment request. */
export const writtenAttachmentUploadMetadataSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    expectedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
    ordinal: z.number().int().min(0).max(9),
  })
  .strict()
export type WrittenAttachmentUploadMetadata = z.infer<typeof writtenAttachmentUploadMetadataSchema>

export const createWrittenAttachmentResponseSchema = z
  .object(writtenEntryMutationShape)
  .strict()
  .superRefine((response, context) => {
    if (
      response.entry.state !== 'draft' ||
      response.entry.attachments.length === 0 ||
      response.entry.attachments.some((attachment) => attachment.uploadStatus !== 'stored')
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment response must expose a stored image on the Student draft',
        path: ['entry', 'attachments'],
      })
    }
  })
export type CreateWrittenAttachmentResponse = z.infer<typeof createWrittenAttachmentResponseSchema>

export const submitWrittenEntryRequestSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    idempotencyKey: z.uuid(),
    expectedEntryVersion: z.number().int().positive(),
    expectedThreadVersion: z.number().int().positive(),
    attachmentIds: z.array(publicIdSchema).max(10),
  })
  .strict()
  .superRefine((request, context) => {
    if (new Set(request.attachmentIds).size !== request.attachmentIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Attachment IDs must be unique',
        path: ['attachmentIds'],
      })
    }
  })
export type SubmitWrittenEntryRequest = z.infer<typeof submitWrittenEntryRequestSchema>

export const submitWrittenEntryResponseSchema = z
  .object({
    ...writtenEntryMutationShape,
    clockSuspicious: z.boolean(),
  })
  .strict()
  .superRefine((response, context) => {
    if (response.threadStatus !== 'awaiting_review' || response.entry.state !== 'submitted') {
      context.addIssue({
        code: 'custom',
        message: 'Submit response must expose material awaiting review',
        path: ['threadStatus'],
      })
    }
  })
export type SubmitWrittenEntryResponse = z.infer<typeof submitWrittenEntryResponseSchema>

export const writtenThreadResponseSchema = z
  .object({
    schemaVersion: contractVersionSchema,
    problemId: publicIdSchema,
    thread: writtenThreadSchema.nullable(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strict()
  .superRefine((response, context) => {
    if (response.thread !== null && response.thread.problemId !== response.problemId) {
      context.addIssue({
        code: 'custom',
        message: 'Thread must belong to the requested problem',
        path: ['thread', 'problemId'],
      })
    }
  })
export type WrittenThreadResponse = z.infer<typeof writtenThreadResponseSchema>

export const writtenSubmissionQueryKeys = {
  all: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'written-submissions'] as const,
  thread: (principal: PrincipalQueryScope, problemId: string) =>
    [
      ...writtenSubmissionQueryKeys.all(principal),
      'thread',
      publicIdSchema.parse(problemId),
    ] as const,
} as const

export const writtenSubmissionFixtureSchema = z
  .object({
    fixtureVersion: contractVersionSchema,
    createRequest: createWrittenEntryRequestSchema,
    createResponse: createWrittenEntryResponseSchema,
    attachmentMetadata: writtenAttachmentUploadMetadataSchema,
    attachmentResponse: createWrittenAttachmentResponseSchema,
    submitRequest: submitWrittenEntryRequestSchema,
    submitResponse: submitWrittenEntryResponseSchema,
    threadResponse: writtenThreadResponseSchema,
  })
  .strict()
