import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const versionSchema = z.literal(1)
export const telegramBindingOwnerTypeSchema = z.enum(['course', 'group'])
export const telegramBindingPurposeSchema = z.enum(['news_source', 'materials_target'])
export const telegramBindingStatusSchema = z.enum(['draft', 'verified', 'disabled'])

export const telegramBindingSchema = z
  .object({
    publicId: publicIdSchema,
    ownerType: telegramBindingOwnerTypeSchema,
    ownerId: publicIdSchema,
    ownerName: z.string().trim().min(1),
    courseId: publicIdSchema,
    courseName: z.string().trim().min(1),
    purpose: telegramBindingPurposeSchema,
    chatId: z
      .number()
      .int()
      .safe()
      .refine((value) => value !== 0),
    messageThreadId: z.number().int().positive().safe().nullable(),
    titleCached: z.string().trim().min(1).max(200).nullable(),
    status: telegramBindingStatusSchema,
    verifiedAt: z.iso.datetime().nullable(),
    createdAt: z.iso.datetime(),
    updatedAt: z.iso.datetime(),
    version: z.number().int().positive(),
  })
  .strip()
  .superRefine((value, context) => {
    if (value.status === 'verified' && value.verifiedAt === null) {
      context.addIssue({
        code: 'custom',
        path: ['verifiedAt'],
        message: 'Verified binding requires verification time',
      })
    }
  })
export type TelegramBinding = z.infer<typeof telegramBindingSchema>

export const telegramBindingListResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    items: z.array(telegramBindingSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type TelegramBindingListResponse = z.infer<typeof telegramBindingListResponseSchema>

export const telegramBindingResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    binding: telegramBindingSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type TelegramBindingResponse = z.infer<typeof telegramBindingResponseSchema>

const bindingOwnerStatusSchema = z.enum(['draft', 'active', 'archived'])
export const telegramBindingOwnersResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    courses: z.array(
      z
        .object({
          courseId: publicIdSchema,
          courseName: z.string().trim().min(1),
          status: bindingOwnerStatusSchema,
          groups: z.array(
            z
              .object({
                groupId: publicIdSchema,
                groupName: z.string().trim().min(1),
                status: bindingOwnerStatusSchema,
              })
              .strip(),
          ),
        })
        .strip(),
    ),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type TelegramBindingOwnersResponse = z.infer<typeof telegramBindingOwnersResponseSchema>

export const saveTelegramBindingRequestSchema = z
  .object({
    schemaVersion: versionSchema,
    ownerType: telegramBindingOwnerTypeSchema,
    ownerId: publicIdSchema,
    purpose: telegramBindingPurposeSchema,
    chatId: z
      .number()
      .int()
      .safe()
      .refine((value) => value !== 0),
    messageThreadId: z.number().int().positive().safe().nullable(),
    titleCached: z.string().trim().min(1).max(200).nullable(),
  })
  .strict()
export type SaveTelegramBindingRequest = z.infer<typeof saveTelegramBindingRequestSchema>

export const changeTelegramBindingStatusRequestSchema = z
  .object({ schemaVersion: versionSchema })
  .strict()

export const telegramBindingQueryKeys = {
  list: (principal: PrincipalQueryScope, courseId?: string) =>
    ['telegram-bindings', ...principalQueryKey(principal), { courseId: courseId ?? null }] as const,
} as const
