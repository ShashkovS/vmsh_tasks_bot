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
  'group_announcement',
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
  .strip()
export type NotificationEvent = z.infer<typeof notificationEventSchema>

export const notificationEventListResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    items: z.array(notificationEventSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type NotificationEventListResponse = z.infer<typeof notificationEventListResponseSchema>

export const familyDigestPreviewSchema = z
  .object({
    groupLessonId: publicIdSchema,
    courseId: publicIdSchema,
    courseName: z.string().trim().min(1),
    groupId: publicIdSchema,
    groupName: z.string().trim().min(1),
    lessonNumber: z.number().int().nonnegative(),
    studentCount: z.number().int().nonnegative(),
    familyCount: z.number().int().nonnegative(),
    alreadySentFamilyCount: z.number().int().nonnegative(),
    pendingFamilyCount: z.number().int().nonnegative(),
    unlinkedStudents: z.array(
      z
        .object({
          studentId: publicIdSchema,
          displayName: z.string().trim().min(1),
        })
        .strip(),
    ),
  })
  .strip()
  .superRefine((value, context) => {
    if (value.alreadySentFamilyCount + value.pendingFamilyCount !== value.familyCount) {
      context.addIssue({
        code: 'custom',
        message: 'Family digest counts do not add up',
        path: ['pendingFamilyCount'],
      })
    }
    if (value.unlinkedStudents.length > value.studentCount) {
      context.addIssue({
        code: 'custom',
        message: 'Unlinked students exceed the lesson group',
        path: ['unlinkedStudents'],
      })
    }
  })
export type FamilyDigestPreview = z.infer<typeof familyDigestPreviewSchema>

export const familyDigestPreviewResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    digest: familyDigestPreviewSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type FamilyDigestPreviewResponse = z.infer<typeof familyDigestPreviewResponseSchema>

export const sendFamilyDigestRequestSchema = z.object({ schemaVersion: versionSchema }).strict()
export type SendFamilyDigestRequest = z.infer<typeof sendFamilyDigestRequestSchema>

export const sendFamilyDigestResponseSchema = familyDigestPreviewResponseSchema
  .extend({ createdFamilyCount: z.number().int().nonnegative() })
  .strip()
  .superRefine((value, context) => {
    if (value.createdFamilyCount > value.digest.familyCount) {
      context.addIssue({
        code: 'custom',
        message: 'Created Family events exceed eligible recipients',
        path: ['createdFamilyCount'],
      })
    }
  })
export type SendFamilyDigestResponse = z.infer<typeof sendFamilyDigestResponseSchema>

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
  .strip()
export type NotificationPreference = z.infer<typeof notificationPreferenceSchema>

export const notificationPreferenceListResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    items: z.array(notificationPreferenceSchema).length(notificationCategorySchema.options.length),
    requestId: z.string().trim().min(1),
  })
  .strip()
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
  .strip()
export type NotificationPreferenceResponse = z.infer<typeof notificationPreferenceResponseSchema>

export const courseNotificationPreferenceSchema = z
  .object({
    category: notificationCategorySchema,
    pushEnabled: z.boolean(),
    inherited: z.boolean(),
    updatedAt: z.iso.datetime().nullable(),
  })
  .strip()
export type CourseNotificationPreference = z.infer<typeof courseNotificationPreferenceSchema>

export const courseNotificationPreferenceListResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    courseId: publicIdSchema,
    items: z
      .array(courseNotificationPreferenceSchema)
      .length(notificationCategorySchema.options.length),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type CourseNotificationPreferenceListResponse = z.infer<
  typeof courseNotificationPreferenceListResponseSchema
>

export const updateCourseNotificationPreferenceRequestSchema = z
  .object({
    schemaVersion: versionSchema,
    category: notificationCategorySchema,
    pushEnabled: z.boolean().nullable(),
  })
  .strict()
export type UpdateCourseNotificationPreferenceRequest = z.infer<
  typeof updateCourseNotificationPreferenceRequestSchema
>

export const courseNotificationPreferenceResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    courseId: publicIdSchema,
    preference: courseNotificationPreferenceSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type CourseNotificationPreferenceResponse = z.infer<
  typeof courseNotificationPreferenceResponseSchema
>

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
  .strip()
export type AcknowledgeNotificationResponse = z.infer<typeof acknowledgeNotificationResponseSchema>

const pushKeySchema = z
  .string()
  .min(20)
  .max(256)
  .regex(/^[A-Za-z0-9_-]+$/)

export const pushSubscriptionConfigResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    enabled: z.boolean(),
    applicationServerKey: pushKeySchema.nullable(),
    requestId: z.string().trim().min(1),
  })
  .strip()
  .superRefine((value, context) => {
    if (value.enabled !== (value.applicationServerKey !== null)) {
      context.addIssue({
        code: 'custom',
        message: 'Enabled Web Push requires an application server key',
        path: ['applicationServerKey'],
      })
    }
  })
export type PushSubscriptionConfigResponse = z.infer<typeof pushSubscriptionConfigResponseSchema>

export const savePushSubscriptionRequestSchema = z
  .object({
    schemaVersion: versionSchema,
    endpoint: z.url().refine((value) => new URL(value).protocol === 'https:'),
    expirationTime: z.number().int().positive().safe().nullable(),
    keys: z
      .object({
        p256dh: pushKeySchema,
        auth: pushKeySchema,
      })
      .strict(),
  })
  .strict()
export type SavePushSubscriptionRequest = z.infer<typeof savePushSubscriptionRequestSchema>

export const savePushSubscriptionResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    subscriptionId: publicIdSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type SavePushSubscriptionResponse = z.infer<typeof savePushSubscriptionResponseSchema>

export const deletePushSubscriptionRequestSchema = z
  .object({
    schemaVersion: versionSchema,
    endpoint: z.url().refine((value) => new URL(value).protocol === 'https:'),
  })
  .strict()
export type DeletePushSubscriptionRequest = z.infer<typeof deletePushSubscriptionRequestSchema>

export const deletePushSubscriptionResponseSchema = z
  .object({
    schemaVersion: versionSchema,
    deleted: z.boolean(),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type DeletePushSubscriptionResponse = z.infer<typeof deletePushSubscriptionResponseSchema>

export const nativePushPayloadSchema = z
  .object({
    schemaVersion: versionSchema,
    eventId: publicIdSchema,
    category: notificationCategorySchema,
    title: z.string().trim().min(1).max(120),
    body: z.string().trim().min(1).max(500),
    route: z.string().startsWith('/'),
    silent: z.boolean(),
    occurredAt: z.iso.datetime(),
  })
  .strip()
export type NativePushPayload = z.infer<typeof nativePushPayloadSchema>

export const notificationQueryKeys = {
  events: (principal: PrincipalQueryScope, unreadOnly = false) =>
    ['notifications', ...principalQueryKey(principal), 'events', { unreadOnly }] as const,
  preferences: (principal: PrincipalQueryScope) =>
    ['notifications', ...principalQueryKey(principal), 'preferences'] as const,
  coursePreferences: (principal: PrincipalQueryScope, courseId: string) =>
    ['notifications', ...principalQueryKey(principal), 'course', courseId, 'preferences'] as const,
  pushConfig: (principal: PrincipalQueryScope) =>
    ['notifications', ...principalQueryKey(principal), 'push-config'] as const,
  familyDigest: (principal: PrincipalQueryScope, groupLessonId: string) =>
    ['notifications', ...principalQueryKey(principal), 'family-digest', groupLessonId] as const,
} as const
