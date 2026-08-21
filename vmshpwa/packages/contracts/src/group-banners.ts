import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { richDocumentCommandSchema, richDocumentSchema } from './rich-document'

export const groupBannerAudienceSchema = z.enum(['student', 'family', 'both'])
export type GroupBannerAudience = z.infer<typeof groupBannerAudienceSchema>

export const groupBannerStatusSchema = z.enum(['active', 'cancelled'])
export type GroupBannerStatus = z.infer<typeof groupBannerStatusSchema>

export const groupBannerOwnerSchema = z
  .object({
    groupId: publicIdSchema,
    name: z.string().trim().min(1).max(200),
    courseId: publicIdSchema,
    courseName: z.string().trim().min(1).max(200),
  })
  .strip()
export type GroupBannerOwner = z.infer<typeof groupBannerOwnerSchema>

export const groupBannerSchema = z
  .object({
    bannerId: publicIdSchema,
    group: groupBannerOwnerSchema,
    audience: groupBannerAudienceSchema,
    html: z.string().min(1).max(5_000),
    markdown: z.string().max(32_768).nullable().optional(),
    document: richDocumentSchema.nullable().optional(),
    startsAt: z.iso.datetime(),
    endsAt: z.iso.datetime(),
    priority: z.number().int().min(-100).max(100),
    dismissible: z.boolean(),
    status: groupBannerStatusSchema,
    version: z.number().int().positive(),
  })
  .strip()
  .superRefine((banner, context) => {
    if (banner.endsAt <= banner.startsAt) {
      context.addIssue({
        code: 'custom',
        message: 'Banner end must follow start',
        path: ['endsAt'],
      })
    }
  })
export type GroupBanner = z.infer<typeof groupBannerSchema>

export const groupBannerListResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(groupBannerSchema),
    requestId: z.string().min(1),
  })
  .strip()
export type GroupBannerListResponse = z.infer<typeof groupBannerListResponseSchema>

export const groupBannerResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    item: groupBannerSchema,
    requestId: z.string().min(1),
  })
  .strip()
export type GroupBannerResponse = z.infer<typeof groupBannerResponseSchema>

const saveGroupBannerV1RequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    groupId: publicIdSchema,
    audience: groupBannerAudienceSchema,
    html: z.string().trim().min(1).max(5_000),
    startsAt: z.iso.datetime(),
    endsAt: z.iso.datetime(),
    priority: z.number().int().min(-100).max(100),
    dismissible: z.boolean(),
  })
  .strict()
  .superRefine((banner, context) => {
    if (banner.endsAt <= banner.startsAt) {
      context.addIssue({
        code: 'custom',
        message: 'Banner end must follow start',
        path: ['endsAt'],
      })
    }
  })
export const saveGroupBannerRequestSchema = z.union([
  saveGroupBannerV1RequestSchema,
  z
    .object({
      groupId: publicIdSchema,
      audience: groupBannerAudienceSchema,
      startsAt: z.iso.datetime(),
      endsAt: z.iso.datetime(),
      priority: z.number().int().min(-100).max(100),
      dismissible: z.boolean(),
    })
    .extend(richDocumentCommandSchema.shape)
    .strict()
    .superRefine((banner, context) => {
      if (banner.endsAt <= banner.startsAt)
        context.addIssue({
          code: 'custom',
          message: 'Banner end must follow start',
          path: ['endsAt'],
        })
    }),
])
export type SaveGroupBannerRequest = z.infer<typeof saveGroupBannerRequestSchema>

const updateGroupBannerV1RequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    audience: groupBannerAudienceSchema,
    html: z.string().trim().min(1).max(5_000),
    startsAt: z.iso.datetime(),
    endsAt: z.iso.datetime(),
    priority: z.number().int().min(-100).max(100),
    dismissible: z.boolean(),
  })
  .strict()
  .superRefine((banner, context) => {
    if (banner.endsAt <= banner.startsAt) {
      context.addIssue({
        code: 'custom',
        message: 'Banner end must follow start',
        path: ['endsAt'],
      })
    }
  })
export const updateGroupBannerRequestSchema = z.union([
  updateGroupBannerV1RequestSchema,
  z
    .object({
      audience: groupBannerAudienceSchema,
      startsAt: z.iso.datetime(),
      endsAt: z.iso.datetime(),
      priority: z.number().int().min(-100).max(100),
      dismissible: z.boolean(),
    })
    .extend(richDocumentCommandSchema.shape)
    .strict()
    .superRefine((banner, context) => {
      if (banner.endsAt <= banner.startsAt)
        context.addIssue({
          code: 'custom',
          message: 'Banner end must follow start',
          path: ['endsAt'],
        })
    }),
])
export type UpdateGroupBannerRequest = z.infer<typeof updateGroupBannerRequestSchema>

export const cancelGroupBannerRequestSchema = z.object({ schemaVersion: z.literal(1) }).strict()

export const groupBannerQueryKeys = {
  active: (principal: PrincipalQueryScope) => ['banners', ...principalQueryKey(principal)] as const,
  staff: (principal: PrincipalQueryScope) =>
    ['group-banners', ...principalQueryKey(principal)] as const,
}
