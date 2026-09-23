import { z } from 'zod'

import { publicIdSchema } from './auth'
import { lessonRichDocumentSchema } from './lesson-rich-document'

export const lessonBlockPositionSchema = z.enum(['before', 'after'])
export type LessonBlockPosition = z.infer<typeof lessonBlockPositionSchema>
export const lessonBlockPublishModeSchema = z.enum(['now', 'scheduled', 'with_lesson'])
export type LessonBlockPublishMode = z.infer<typeof lessonBlockPublishModeSchema>

export const lessonBlockRevisionSchema = z
  .object({
    revisionId: publicIdSchema,
    revisionNumber: z.number().int().positive(),
    markdown: z.string().max(32_768),
    document: lessonRichDocumentSchema.nullable(),
    createdAt: z.iso.datetime(),
  })
  .strip()
export type LessonBlockRevision = z.infer<typeof lessonBlockRevisionSchema>

export const publishedLessonBlockSchema = z
  .object({
    blockId: publicIdSchema,
    revisionId: publicIdSchema,
    position: lessonBlockPositionSchema,
    version: z.number().int().positive(),
    publishedAt: z.iso.datetime(),
    document: lessonRichDocumentSchema,
  })
  .strip()
export type PublishedLessonBlock = z.infer<typeof publishedLessonBlockSchema>

export const publishedLessonBlocksSchema = z
  .object({
    before: publishedLessonBlockSchema.nullable(),
    after: publishedLessonBlockSchema.nullable(),
  })
  .strip()
  .superRefine((blocks, context) => {
    if (blocks.before?.position !== undefined && blocks.before.position !== 'before') {
      context.addIssue({
        code: 'custom',
        message: 'The before slot must contain a before block',
        path: ['before', 'position'],
      })
    }
    if (blocks.after?.position !== undefined && blocks.after.position !== 'after') {
      context.addIssue({
        code: 'custom',
        message: 'The after slot must contain an after block',
        path: ['after', 'position'],
      })
    }
  })
export type PublishedLessonBlocks = z.infer<typeof publishedLessonBlocksSchema>

export const staffLessonBlockSchema = z
  .object({
    blockId: publicIdSchema,
    position: lessonBlockPositionSchema,
    version: z.number().int().positive(),
    draft: lessonBlockRevisionSchema.nullable(),
    published: lessonBlockRevisionSchema.nullable(),
    publishedAt: z.iso.datetime().nullable(),
    pending: lessonBlockRevisionSchema.nullable(),
    pendingMode: z.enum(['scheduled', 'with_lesson']).nullable(),
    scheduledAt: z.iso.datetime().nullable(),
    etag: z.string().min(1),
  })
  .strip()
export type StaffLessonBlock = z.infer<typeof staffLessonBlockSchema>

export const staffLessonBlocksResponseSchema = z
  .object({
    groupLessonId: publicIdSchema,
    businessTimezone: z.string().trim().min(1),
    before: staffLessonBlockSchema.nullable(),
    after: staffLessonBlockSchema.nullable(),
  })
  .strip()
export type StaffLessonBlocksResponse = z.infer<typeof staffLessonBlocksResponseSchema>

export const saveLessonBlockDraftRequestSchema = z
  .object({
    markdown: z.string().max(32_768),
    document: lessonRichDocumentSchema.nullable(),
  })
  .strict()
export type SaveLessonBlockDraftRequest = z.infer<typeof saveLessonBlockDraftRequestSchema>

export const publishLessonBlockRequestSchema = z
  .object({
    revisionId: publicIdSchema,
    mode: lessonBlockPublishModeSchema,
    scheduledAt: z.iso.datetime().nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if ((value.mode === 'scheduled') !== (value.scheduledAt !== null)) {
      context.addIssue({
        code: 'custom',
        message: 'Only scheduled publication has scheduledAt',
        path: ['scheduledAt'],
      })
    }
  })
export type PublishLessonBlockRequest = z.infer<typeof publishLessonBlockRequestSchema>

export const lessonBlockQueryKeys = {
  staff: (groupLessonId: string) =>
    ['lesson-blocks', publicIdSchema.parse(groupLessonId), 'staff'] as const,
  reader: (groupLessonId: string) =>
    ['lesson-blocks', publicIdSchema.parse(groupLessonId)] as const,
}
