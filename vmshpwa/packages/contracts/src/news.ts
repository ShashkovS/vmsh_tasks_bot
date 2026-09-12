import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { richDocumentCommandSchema, richDocumentSchema } from './rich-document'

/** Wire format for authenticated news reads. See Phase 8 in
 * `dev/development-plan/12-phase-8-news-and-notifications.md`.
 */
export const newsEntitySchema = z
  .object({
    type: z.enum([
      'bold',
      'italic',
      'underline',
      'strike',
      'code',
      'link',
      'spoiler',
      'mark',
      'sub',
      'sup',
    ]),
    offset: z.number().int().nonnegative(),
    length: z.number().int().positive(),
    href: z.string().min(1).optional(),
  })
  .strip()
export type NewsEntity = z.infer<typeof newsEntitySchema>

export const newsTextBlockSchema = z
  .object({
    kind: z.literal('text'),
    text: z.string(),
    entities: z.array(newsEntitySchema).optional(),
  })
  .strip()
export type NewsTextBlock = z.infer<typeof newsTextBlockSchema>

const publicMediaUrlSchema = z
  .url()
  .refine((value) => ['http:', 'https:'].includes(new URL(value).protocol))
  .nullable()

const newsMediaCommon = {
  mediaId: publicIdSchema,
  previewUrl: publicMediaUrlSchema,
}

export const newsMediaSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('photo'), ...newsMediaCommon, alt: z.string() }).strip(),
  z.object({ kind: z.literal('video'), ...newsMediaCommon }).strip(),
  z
    .object({
      kind: z.literal('document'),
      mediaId: publicIdSchema,
      name: z.string().trim().min(1),
      url: publicMediaUrlSchema,
    })
    .strip(),
])
export type NewsMedia = z.infer<typeof newsMediaSchema>

export const newsPostSchema = z
  .object({
    postId: publicIdSchema,
    source: z.enum(['telegram', 'local']),
    publishedAt: z.iso.datetime(),
    editedAt: z.iso.datetime().nullable(),
    revision: z.number().int().positive(),
    state: z.enum(['published', 'source-revised']),
    attribution: z
      .object({ channel: z.string().trim().min(1).max(200) })
      .strip()
      .nullable(),
    blocks: z.array(newsTextBlockSchema).min(1),
    media: z.array(newsMediaSchema),
    // Returned only for contentVersion=2 reads. v1 clients intentionally ignore it.
    document: richDocumentSchema.optional(),
  })
  .strip()
export type NewsPost = z.infer<typeof newsPostSchema>

export const newsFeedResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(newsPostSchema),
    nextCursor: publicIdSchema.nullable(),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type NewsFeedResponse = z.infer<typeof newsFeedResponseSchema>

export const newsPostResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    item: newsPostSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type NewsPostResponse = z.infer<typeof newsPostResponseSchema>

export const newsQueryKeys = {
  feed: (principal: PrincipalQueryScope) =>
    ['news', ...principalQueryKey(principal), 'feed'] as const,
  post: (principal: PrincipalQueryScope, postId: string) =>
    ['news', ...principalQueryKey(principal), 'post', publicIdSchema.parse(postId)] as const,
  moderation: (principal: PrincipalQueryScope, state: StaffNewsVisibilityFilter) =>
    ['news', ...principalQueryKey(principal), 'moderation', state] as const,
} as const

export const staffNewsVisibilitySchema = z.enum(['visible', 'manual_hidden', 'source_deleted'])
export type StaffNewsVisibility = z.infer<typeof staffNewsVisibilitySchema>
export const staffNewsVisibilityFilterSchema = z.enum(['all', ...staffNewsVisibilitySchema.options])
export type StaffNewsVisibilityFilter = z.infer<typeof staffNewsVisibilityFilterSchema>

export const staffNewsItemSchema = z
  .object({
    postId: publicIdSchema,
    source: z.enum(['telegram', 'local']),
    channelTitle: z.string().trim().min(1).max(200).nullable(),
    ownerType: z.enum(['course', 'group']),
    ownerId: publicIdSchema,
    ownerName: z.string().trim().min(1).max(200),
    publishedAt: z.iso.datetime(),
    editedAt: z.iso.datetime().nullable(),
    revision: z.number().int().positive(),
    textExcerpt: z.string().max(500),
    editableText: z.string().max(32_768).nullable(),
    markdown: z.string().max(32_768).nullable().optional(),
    document: richDocumentSchema.nullable().optional(),
    mediaCount: z.number().int().nonnegative(),
    visibility: staffNewsVisibilitySchema,
    moderationReason: z.string().trim().min(1).max(500).nullable(),
    visibilityUpdatedAt: z.iso.datetime(),
    isScheduled: z.boolean(),
    version: z.number().int().positive(),
  })
  .strip()
export type StaffNewsItem = z.infer<typeof staffNewsItemSchema>

export const staffNewsListResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(staffNewsItemSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type StaffNewsListResponse = z.infer<typeof staffNewsListResponseSchema>

export const changeNewsVisibilityRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    state: z.enum(['visible', 'manual_hidden']),
    reason: z.string().trim().min(1).max(500).nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.state === 'visible' && value.reason !== null) {
      context.addIssue({
        code: 'custom',
        path: ['reason'],
        message: 'A visible post cannot keep a moderation reason',
      })
    }
  })
export type ChangeNewsVisibilityRequest = z.infer<typeof changeNewsVisibilityRequestSchema>

export const reconcileNewsSourceRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    sourceState: z.enum(['deleted', 'present']),
    reason: z.string().trim().min(1).max(500),
  })
  .strict()
export type ReconcileNewsSourceRequest = z.infer<typeof reconcileNewsSourceRequestSchema>

const createLocalNewsV1RequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    ownerType: z.enum(['course', 'group']),
    ownerId: publicIdSchema,
    text: z.string().trim().min(1).max(32_768),
    publishedAt: z.iso.datetime({ offset: true }),
  })
  .strict()
export const createLocalNewsRequestSchema = z.union([
  createLocalNewsV1RequestSchema,
  z
    .object({
      ownerType: z.enum(['course', 'group']),
      ownerId: publicIdSchema,
      publishedAt: z.iso.datetime({ offset: true }),
    })
    .extend(richDocumentCommandSchema.shape)
    .strict(),
])
export type CreateLocalNewsRequest = z.infer<typeof createLocalNewsRequestSchema>

const updateLocalNewsV1RequestSchema = z.union([
  z
    .object({
      schemaVersion: z.literal(1),
      text: z.string().trim().min(1).max(32_768),
      publishedAt: z.iso.datetime({ offset: true }),
    })
    .strict(),
  z
    .object({
      schemaVersion: z.literal(1),
      text: z.string().trim().min(1).max(32_768),
    })
    .strict(),
])
export const updateLocalNewsRequestSchema = z.union([
  updateLocalNewsV1RequestSchema,
  z
    .object({ publishedAt: z.iso.datetime({ offset: true }).optional() })
    .extend(richDocumentCommandSchema.shape)
    .strict(),
])
export type UpdateLocalNewsRequest = z.infer<typeof updateLocalNewsRequestSchema>

export const staffNewsItemResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    item: staffNewsItemSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type StaffNewsItemResponse = z.infer<typeof staffNewsItemResponseSchema>
