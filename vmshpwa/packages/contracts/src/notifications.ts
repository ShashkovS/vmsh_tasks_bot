import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

export const NOTIFICATION_CONTRACT_VERSION = 1 as const
const versionSchema = z.literal(NOTIFICATION_CONTRACT_VERSION)

export const notificationCategorySchema = z.enum([
  'lesson_published',
  'hint_published',
  'solution_published',
  'review_completed',
  'thread_updated',
  'oral_window',
  'classroom_assignment',
  'deadline',
  'news',
])
export type NotificationCategory = z.infer<typeof notificationCategorySchema>

export const notificationEventSchema = z
  .object({
    eventId: publicIdSchema,
    category: notificationCategorySchema,
    route: z.string().startsWith('/'),
    payload: z.record(z.string(), z.unknown()),
    occurredAt: z.iso.datetime(),
    deliverAfter: z.iso.datetime(),
    readAt: z.iso.datetime().nullable(),
  })
  .strict()
export type NotificationEvent = z.infer<typeof notificationEventSchema>

export const notificationEventListResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    items: z.array(notificationEventSchema),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type NotificationEventListResponse = z.infer<typeof notificationEventListResponseSchema>

export const notificationPreferenceSchema = z
  .object({
    category: notificationCategorySchema,
    inAppEnabled: z.boolean(),
    pushEnabled: z.boolean(),
    soundEnabled: z.boolean(),
    quietStartsLocal: z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d$/),
    quietEndsLocal: z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d$/),
    timezone: z.string().trim().min(1),
    updatedAt: z.iso.datetime().nullable(),
  })
  .strict()
export type NotificationPreference = z.infer<typeof notificationPreferenceSchema>

export const notificationPreferenceListResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    items: z.array(notificationPreferenceSchema).length(notificationCategorySchema.options.length),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type NotificationPreferenceListResponse = z.infer<
  typeof notificationPreferenceListResponseSchema
>

export const updateNotificationPreferenceRequestSchema = notificationPreferenceSchema
  .omit({ updatedAt: true })
  .extend({ schemaVersion: versionSchema })
  .strict()
export type UpdateNotificationPreferenceRequest = z.infer<
  typeof updateNotificationPreferenceRequestSchema
>

export const notificationPreferenceResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    preference: notificationPreferenceSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type NotificationPreferenceResponse = z.infer<typeof notificationPreferenceResponseSchema>

export const acknowledgeNotificationRequestSchema = z
  .object({ schemaVersion: versionSchema })
  .strict()
export const acknowledgeNotificationResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    eventId: publicIdSchema,
    readAt: z.iso.datetime(),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AcknowledgeNotificationResponse = z.infer<typeof acknowledgeNotificationResponseSchema>

export const notificationQueryKeys = {
  events: (principal: PrincipalQueryScope, unreadOnly = false) =>
    ['notifications', ...principalQueryKey(principal), 'events', { unreadOnly }] as const,
  preferences: (principal: PrincipalQueryScope) =>
    ['notifications', ...principalQueryKey(principal), 'preferences'] as const,
} as const
