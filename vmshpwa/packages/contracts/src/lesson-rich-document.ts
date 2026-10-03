import { z } from 'zod'

import {
  richBlockSchema,
  richDocumentSchema,
  richMediaSchema,
  type RichBlock,
  type RichMedia,
} from './rich-document'

const youtubeVideoIdSchema = z.string().regex(/^[A-Za-z0-9_-]{11}$/)
const vkSignedIdSchema = z.string().regex(/^-?[1-9]\d{0,19}$/)
const vkPositiveIdSchema = z.string().regex(/^[1-9]\d{0,19}$/)
const videoTitleSchema = z.string().trim().min(1).max(200).nullable()

export const lessonVideoBlockSchema = z.discriminatedUnion('provider', [
  z
    .object({
      type: z.literal('video'),
      provider: z.literal('youtube'),
      videoId: youtubeVideoIdSchema,
      startSeconds: z.number().int().min(0).max(604_800),
      title: videoTitleSchema,
    })
    .strip(),
  z
    .object({
      type: z.literal('video'),
      provider: z.literal('vk'),
      ownerId: vkSignedIdSchema,
      videoId: vkPositiveIdSchema,
      accessHash: z
        .string()
        .regex(/^[A-Za-z0-9_-]{1,256}$/)
        .nullable(),
      hd: z.union([z.literal(0), z.literal(1), z.literal(2), z.literal(3)]),
      title: videoTitleSchema,
    })
    .strip(),
])
export type LessonVideoBlock = z.infer<typeof lessonVideoBlockSchema>

export type LessonRichBlock = RichBlock | LessonVideoBlock

/** RichDocument v1 plus root-level video blocks, only for lesson material. */
export const lessonRichDocumentSchema = z
  .object({
    schemaVersion: z.literal(1),
    blocks: z
      .array(z.union([richBlockSchema, lessonVideoBlockSchema]))
      .min(1)
      .max(1_000),
    media: z.array(richMediaSchema).max(10),
  })
  .strip()
  .superRefine((document, context) => {
    const ordinary = document.blocks.map((block) =>
      block.type === 'video' ? { type: 'divider' } : block,
    )
    const validated = richDocumentSchema.safeParse({ ...document, blocks: ordinary })
    if (!validated.success) {
      for (const issue of validated.error.issues) {
        context.addIssue(
          issue.path === undefined
            ? { code: 'custom', message: issue.message }
            : { code: 'custom', message: issue.message, path: issue.path },
        )
      }
    }
    if (document.blocks.filter((block) => block.type === 'video').length > 20) {
      context.addIssue({
        code: 'custom',
        message: 'At most 20 videos are allowed',
        path: ['blocks'],
      })
    }
  })
export type LessonRichDocument = z.infer<typeof lessonRichDocumentSchema>

export type LessonRichMedia = RichMedia
