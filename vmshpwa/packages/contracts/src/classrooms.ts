import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { attendanceModeSchema } from './courses'

/** Phase-7 Staff classroom-catalog wire contract. */
export const CLASSROOM_CONTRACT_VERSION = 1 as const
const classroomContractVersionSchema = z.literal(CLASSROOM_CONTRACT_VERSION)

export const classroomStatusSchema = z.enum(['active', 'archived'])
export type ClassroomStatus = z.infer<typeof classroomStatusSchema>
export const classroomListStatusSchema = classroomStatusSchema.or(z.literal('all'))
export type ClassroomListStatus = z.infer<typeof classroomListStatusSchema>

export const classroomNameSchema = z
  .string()
  .max(200)
  .refine((value) => value.trim().length > 0, 'Classroom name must not be empty')

export const classroomSchema = z
  .object({
    publicId: publicIdSchema,
    name: z.string().trim().min(1).max(200),
    status: classroomStatusSchema,
    createdAt: z.iso.datetime(),
    updatedAt: z.iso.datetime(),
    version: z.number().int().positive(),
  })
  .strip()
export type Classroom = z.infer<typeof classroomSchema>

export const classroomListQuerySchema = z
  .object({
    search: z.string().max(200).default(''),
    status: classroomListStatusSchema.default('active'),
  })
  .strict()
export type ClassroomListQuery = z.input<typeof classroomListQuerySchema>

export const createClassroomRequestSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    name: classroomNameSchema,
  })
  .strict()
export type CreateClassroomRequest = z.infer<typeof createClassroomRequestSchema>

export const renameClassroomRequestSchema = createClassroomRequestSchema
export type RenameClassroomRequest = z.infer<typeof renameClassroomRequestSchema>

export const changeClassroomStatusRequestSchema = z
  .object({ schemaVersion: classroomContractVersionSchema })
  .strict()
export type ChangeClassroomStatusRequest = z.infer<typeof changeClassroomStatusRequestSchema>

export const classroomResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    classroom: classroomSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomResponse = z.infer<typeof classroomResponseSchema>

export const classroomListResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    items: z.array(classroomSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomListResponse = z.infer<typeof classroomListResponseSchema>

export const inPersonEventStatusSchema = z.enum(['draft', 'scheduled', 'completed', 'cancelled'])
export type InPersonEventStatus = z.infer<typeof inPersonEventStatusSchema>
export const classroomLayoutStateSchema = z.enum(['inherited', 'draft', 'confirmed'])

export const classroomLayoutGroupSchema = z
  .object({
    groupLessonPublicId: publicIdSchema,
    coursePublicId: publicIdSchema,
    courseName: z.string().trim().min(1),
    groupPublicId: publicIdSchema,
    groupName: z.string().trim().min(1),
    shortCode: z.string().trim().min(1),
    colorKey: z.string().trim().min(1).nullable(),
    lessonNumber: z.number().int().nonnegative(),
    inPersonCount: z.number().int().nonnegative(),
    assignedCount: z.number().int().nonnegative(),
  })
  .strip()
export type ClassroomLayoutGroup = z.infer<typeof classroomLayoutGroupSchema>

export const inPersonEventGroupSchema = classroomLayoutGroupSchema.omit({ assignedCount: true })
export type InPersonEventGroup = z.infer<typeof inPersonEventGroupSchema>

export const inPersonEventSchema = z
  .object({
    publicId: publicIdSchema,
    name: z.string().trim().min(1).max(200),
    startsAt: z.iso.datetime(),
    endsAt: z.iso.datetime(),
    status: inPersonEventStatusSchema,
    version: z.number().int().positive(),
    groupLessons: z.array(inPersonEventGroupSchema),
  })
  .strip()
export type InPersonEvent = z.infer<typeof inPersonEventSchema>

export const inPersonEventListResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    season: z
      .object({
        publicId: publicIdSchema,
        code: z.string().trim().min(1),
        title: z.string().trim().min(1),
      })
      .strip(),
    events: z.array(inPersonEventSchema),
    candidates: z.array(inPersonEventGroupSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type InPersonEventListResponse = z.infer<typeof inPersonEventListResponseSchema>

export const inPersonEventResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    event: inPersonEventSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type InPersonEventResponse = z.infer<typeof inPersonEventResponseSchema>

export const saveInPersonEventRequestSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    name: z.string().trim().min(1).max(200),
    startsAt: z.iso.datetime(),
    endsAt: z.iso.datetime(),
    status: inPersonEventStatusSchema,
    groupLessonPublicIds: z.array(publicIdSchema).min(1).max(500),
  })
  .strict()
  .refine(
    (request) => new Set(request.groupLessonPublicIds).size === request.groupLessonPublicIds.length,
    { message: 'Group lessons must be unique', path: ['groupLessonPublicIds'] },
  )
  .refine((request) => request.endsAt > request.startsAt, {
    message: 'Event end must be after its start',
    path: ['endsAt'],
  })
export type SaveInPersonEventRequest = z.infer<typeof saveInPersonEventRequestSchema>

export const classroomLayoutRoomSchema = z
  .object({
    classroomPublicId: publicIdSchema,
    classroomName: z.string().trim().min(1).max(200),
    classroomStatus: classroomStatusSchema,
    groupLessonPublicId: publicIdSchema,
    coursePublicId: publicIdSchema,
    groupPublicId: publicIdSchema,
    groupName: z.string().trim().min(1),
    sourceLayoutPublicId: publicIdSchema.nullable(),
  })
  .strip()
export type ClassroomLayoutRoom = z.infer<typeof classroomLayoutRoomSchema>

export const classroomLayoutSchema = z
  .object({
    event: z
      .object({
        publicId: publicIdSchema,
        name: z.string().trim().min(1),
        startsAt: z.iso.datetime(),
        endsAt: z.iso.datetime(),
        status: inPersonEventStatusSchema,
        version: z.number().int().positive(),
      })
      .strip(),
    state: classroomLayoutStateSchema,
    publicId: publicIdSchema.nullable(),
    version: z.number().int().positive().nullable(),
    groups: z.array(classroomLayoutGroupSchema),
    rooms: z.array(classroomLayoutRoomSchema),
    conflicts: z.array(
      z
        .object({
          classroomPublicId: publicIdSchema,
          classroomName: z.string().trim().min(1).max(200),
        })
        .strip(),
    ),
  })
  .strip()
  .superRefine((layout, context) => {
    const virtual = layout.state === 'inherited'
    if (virtual !== (layout.publicId === null && layout.version === null)) {
      context.addIssue({
        code: 'custom',
        message:
          'Inherited layout must be virtual; persisted layout must have identity and version',
      })
    }
  })
export type ClassroomLayout = z.infer<typeof classroomLayoutSchema>

export const classroomLayoutResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    layout: classroomLayoutSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomLayoutResponse = z.infer<typeof classroomLayoutResponseSchema>

export const materializeClassroomLayoutRequestSchema = z
  .object({ schemaVersion: classroomContractVersionSchema })
  .strict()
export type MaterializeClassroomLayoutRequest = z.infer<
  typeof materializeClassroomLayoutRequestSchema
>

export const replaceClassroomLayoutRequestSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    mappings: z
      .array(
        z
          .object({
            classroomPublicId: publicIdSchema,
            groupLessonPublicId: publicIdSchema,
          })
          .strict(),
      )
      .max(500),
  })
  .strict()
export type ReplaceClassroomLayoutRequest = z.infer<typeof replaceClassroomLayoutRequestSchema>

export const confirmClassroomLayoutRequestSchema = materializeClassroomLayoutRequestSchema
export type ConfirmClassroomLayoutRequest = z.infer<typeof confirmClassroomLayoutRequestSchema>

export const classroomAssignmentPlanStateSchema = z.enum(['draft', 'confirmed', 'stale'])
export const classroomAssignmentStatusSchema = z.enum(['assigned', 'reassigning'])
export const classroomAssignmentSourceSchema = z.enum([
  'previous-room',
  'least-loaded',
  'manual',
  'group-change',
  'mode-change',
  'import',
])

export const classroomAssignmentPlanSchema = z
  .object({
    event: z
      .object({
        publicId: publicIdSchema,
        name: z.string().trim().min(1),
        startsAt: z.iso.datetime(),
        endsAt: z.iso.datetime(),
        status: inPersonEventStatusSchema,
      })
      .strip(),
    plan: z
      .object({
        publicId: publicIdSchema,
        state: classroomAssignmentPlanStateSchema,
        staleReason: z.string().nullable(),
        version: z.number().int().positive(),
        updatedAt: z.iso.datetime(),
        confirmedAt: z.iso.datetime().nullable(),
      })
      .strip()
      .nullable(),
    groups: z.array(classroomLayoutGroupSchema.omit({ assignedCount: true })),
    rooms: z.array(
      z
        .object({
          publicId: publicIdSchema,
          name: z.string().trim().min(1).max(200),
          status: classroomStatusSchema,
          groupLessonPublicId: publicIdSchema,
        })
        .strip(),
    ),
    students: z.array(
      z
        .object({
          enrollmentPublicId: publicIdSchema,
          studentPublicId: publicIdSchema,
          surname: z.string().trim().min(1),
          name: z.string().trim().min(1),
          age: z.number().min(0).max(100).nullable(),
          grade: z.number().int().min(1).max(20).nullable(),
          strength: z.number().min(0).max(10).nullable(),
          groupLessonPublicId: publicIdSchema,
          groupPublicId: publicIdSchema,
          classroomPublicId: publicIdSchema.nullable(),
          classroomName: z.string().trim().min(1).max(200).nullable(),
          status: classroomAssignmentStatusSchema,
          source: classroomAssignmentSourceSchema,
        })
        .strip(),
    ),
  })
  .strip()
export type ClassroomAssignmentPlan = z.infer<typeof classroomAssignmentPlanSchema>

export const classroomAssignmentPlanResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    assignmentPlan: classroomAssignmentPlanSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomAssignmentPlanResponse = z.infer<typeof classroomAssignmentPlanResponseSchema>

export const classroomAssignmentHistoryItemSchema = z
  .object({
    eventPublicId: publicIdSchema,
    eventName: z.string().trim().min(1),
    startsAt: z.iso.datetime(),
    planPublicId: publicIdSchema,
    confirmedAt: z.iso.datetime(),
    classroomPublicId: publicIdSchema,
    classroomName: z.string().trim().min(1).max(200),
    coursePublicId: publicIdSchema,
    courseName: z.string().trim().min(1),
    groupPublicId: publicIdSchema,
    groupName: z.string().trim().min(1),
    groupLessonPublicId: publicIdSchema,
  })
  .strip()
export type ClassroomAssignmentHistoryItem = z.infer<typeof classroomAssignmentHistoryItemSchema>

export const classroomAssignmentHistoryResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    items: z.array(classroomAssignmentHistoryItemSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomAssignmentHistoryResponse = z.infer<
  typeof classroomAssignmentHistoryResponseSchema
>

export const publishedClassroomAssignmentStatusSchema = z.enum([
  'not_applicable',
  'reassigning',
  'assigned',
])
export type PublishedClassroomAssignmentStatus = z.infer<
  typeof publishedClassroomAssignmentStatusSchema
>

export const publishedClassroomAssignmentSchema = z
  .object({
    eventPublicId: publicIdSchema,
    eventName: z.string().trim().min(1),
    startsAt: z.iso.datetime(),
    endsAt: z.iso.datetime(),
    coursePublicId: publicIdSchema,
    courseName: z.string().trim().min(1),
    groupPublicId: publicIdSchema,
    groupName: z.string().trim().min(1),
    groupLessonPublicId: publicIdSchema,
    attendanceMode: attendanceModeSchema,
    status: publishedClassroomAssignmentStatusSchema,
    classroomPublicId: publicIdSchema.nullable(),
    classroomName: z.string().trim().min(1).max(200).nullable(),
    confirmedAt: z.iso.datetime().nullable(),
    announcedAt: z.iso.datetime().nullable(),
  })
  .strip()
  .superRefine((item, context) => {
    const hasClassroom = item.classroomPublicId !== null && item.classroomName !== null
    if ((item.status === 'assigned') !== hasClassroom) {
      context.addIssue({
        code: 'custom',
        message: 'Only an assigned classroom state may contain a classroom',
      })
    }
    if (item.status === 'assigned' && item.confirmedAt === null) {
      context.addIssue({
        code: 'custom',
        message: 'An assigned classroom state must identify its confirmation time',
      })
    }
    if (item.status !== 'assigned' && item.announcedAt !== null) {
      context.addIssue({
        code: 'custom',
        message: 'Only an assigned classroom state may be announced',
      })
    }
    if (item.status === 'not_applicable' && item.attendanceMode !== 'online') {
      context.addIssue({
        code: 'custom',
        message: 'Only an online enrollment may be not applicable',
      })
    }
  })
export type PublishedClassroomAssignment = z.infer<typeof publishedClassroomAssignmentSchema>

export const publishedClassroomAssignmentListResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    items: z.array(publishedClassroomAssignmentSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type PublishedClassroomAssignmentListResponse = z.infer<
  typeof publishedClassroomAssignmentListResponseSchema
>

/** Phase-7 explicit Student-only classroom announcement contract. */
export const classroomDeliveryPreviewRecipientSchema = z
  .object({
    studentPublicId: publicIdSchema,
    studentName: z.string().trim().min(1),
    coursePublicId: publicIdSchema,
    courseName: z.string().trim().min(1),
    groupPublicId: publicIdSchema,
    groupName: z.string().trim().min(1),
    classroomPublicId: publicIdSchema,
    classroomName: z.string().trim().min(1).max(200),
    changed: z.boolean(),
    pwaAvailable: z.boolean(),
    telegramAvailable: z.boolean(),
  })
  .strip()

export const classroomDeliveryPreviewSchema = z
  .object({
    planPublicId: publicIdSchema,
    planVersion: z.number().int().positive(),
    previewHash: z.string().regex(/^[a-f0-9]{64}$/),
    recipientCount: z.number().int().nonnegative(),
    changedCount: z.number().int().nonnegative(),
    pwaUnavailableCount: z.number().int().nonnegative(),
    telegramUnavailableCount: z.number().int().nonnegative(),
    recipients: z.array(classroomDeliveryPreviewRecipientSchema),
  })
  .strip()
  .superRefine((preview, context) => {
    if (preview.recipientCount !== preview.recipients.length) {
      context.addIssue({ code: 'custom', message: 'Recipient count must match the preview rows' })
    }
    if (preview.changedCount > preview.recipientCount) {
      context.addIssue({ code: 'custom', message: 'Changed count cannot exceed recipients' })
    }
  })
export type ClassroomDeliveryPreview = z.infer<typeof classroomDeliveryPreviewSchema>

export const classroomDeliveryPreviewResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    preview: classroomDeliveryPreviewSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomDeliveryPreviewResponse = z.infer<
  typeof classroomDeliveryPreviewResponseSchema
>

export const classroomDeliveryChannelSchema = z.enum(['pwa', 'telegram'])
export type ClassroomDeliveryChannel = z.infer<typeof classroomDeliveryChannelSchema>
export const classroomDeliveryChannelStateSchema = z.enum([
  'not_requested',
  'queued',
  'sent',
  'suppressed',
  'failed',
])
export const classroomDeliveryBatchStateSchema = z.enum([
  'queued',
  'completed',
  'completed_with_errors',
])

const classroomDeliveryResultSchema = z
  .object({
    state: classroomDeliveryChannelStateSchema,
    errorCode: z.string().trim().min(1).nullable(),
    sentAt: z.iso.datetime().nullable(),
  })
  .strip()

export const classroomDeliveryChannelReportSchema = z
  .object({
    selected: z.number().int().nonnegative(),
    eligible: z.number().int().nonnegative(),
    suppressed: z.number().int().nonnegative(),
    queued: z.number().int().nonnegative(),
    attempted: z.number().int().nonnegative(),
    succeeded: z.number().int().nonnegative(),
    failed: z.number().int().nonnegative(),
  })
  .strip()

export const classroomDeliveryReportSchema = z
  .object({
    channels: z
      .object({
        pwa: classroomDeliveryChannelReportSchema,
        telegram: classroomDeliveryChannelReportSchema,
      })
      .strip(),
    deliveredAny: z.number().int().nonnegative(),
    deliveredAll: z.number().int().nonnegative(),
    partial: z.number().int().nonnegative(),
  })
  .strip()

export const classroomDeliveryBatchSchema = z
  .object({
    publicId: publicIdSchema,
    planPublicId: publicIdSchema,
    planVersion: z.number().int().positive(),
    previewHash: z.string().regex(/^[a-f0-9]{64}$/),
    channels: z.array(classroomDeliveryChannelSchema).min(1).max(2),
    recipientCount: z.number().int().nonnegative(),
    changedCount: z.number().int().nonnegative(),
    state: classroomDeliveryBatchStateSchema,
    createdAt: z.iso.datetime(),
    completedAt: z.iso.datetime().nullable(),
    version: z.number().int().positive(),
    channelCounts: z
      .object({
        pwa: z.partialRecord(classroomDeliveryChannelStateSchema, z.number().int().nonnegative()),
        telegram: z.partialRecord(
          classroomDeliveryChannelStateSchema,
          z.number().int().nonnegative(),
        ),
      })
      .strip(),
    deliveryReport: classroomDeliveryReportSchema,
    recipients: z.array(
      z
        .object({
          studentPublicId: publicIdSchema,
          studentName: z.string().trim().min(1),
          coursePublicId: publicIdSchema,
          courseName: z.string().trim().min(1),
          groupPublicId: publicIdSchema,
          groupName: z.string().trim().min(1),
          classroomPublicId: publicIdSchema,
          classroomName: z.string().trim().min(1).max(200),
          pwa: classroomDeliveryResultSchema,
          telegram: classroomDeliveryResultSchema,
        })
        .strip(),
    ),
  })
  .strip()
export type ClassroomDeliveryBatch = z.infer<typeof classroomDeliveryBatchSchema>

export const classroomDeliveryBatchResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    batch: classroomDeliveryBatchSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type ClassroomDeliveryBatchResponse = z.infer<typeof classroomDeliveryBatchResponseSchema>

export const latestClassroomDeliveryBatchResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    batch: classroomDeliveryBatchSchema.nullable(),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type LatestClassroomDeliveryBatchResponse = z.infer<
  typeof latestClassroomDeliveryBatchResponseSchema
>

export const createClassroomDeliveryBatchRequestSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    channels: z.array(classroomDeliveryChannelSchema).min(1).max(2),
    expectedPlanVersion: z.number().int().positive(),
    previewHash: z.string().regex(/^[a-f0-9]{64}$/),
    idempotencyKey: z.string().trim().min(1).max(128),
  })
  .strict()
  .refine((request) => new Set(request.channels).size === request.channels.length, {
    message: 'Delivery channels must be unique',
  })
export type CreateClassroomDeliveryBatchRequest = z.infer<
  typeof createClassroomDeliveryBatchRequestSchema
>

export const retryClassroomDeliveryBatchRequestSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    expectedBatchVersion: z.number().int().positive(),
    idempotencyKey: z.string().trim().min(1).max(128),
  })
  .strict()
export type RetryClassroomDeliveryBatchRequest = z.infer<
  typeof retryClassroomDeliveryBatchRequestSchema
>

export const recalculateClassroomAssignmentPlanRequestSchema =
  materializeClassroomLayoutRequestSchema
export type RecalculateClassroomAssignmentPlanRequest = z.infer<
  typeof recalculateClassroomAssignmentPlanRequestSchema
>

export const updateClassroomAssignmentPlanRequestSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    assignments: z
      .array(
        z
          .object({
            enrollmentPublicId: publicIdSchema,
            classroomPublicId: publicIdSchema,
            confirmGroupChange: z.boolean(),
          })
          .strict(),
      )
      .max(2000),
  })
  .strict()
export type UpdateClassroomAssignmentPlanRequest = z.infer<
  typeof updateClassroomAssignmentPlanRequestSchema
>

export const confirmClassroomAssignmentPlanRequestSchema = materializeClassroomLayoutRequestSchema
export type ConfirmClassroomAssignmentPlanRequest = z.infer<
  typeof confirmClassroomAssignmentPlanRequestSchema
>

export function classroomEtag(classroom: Pick<Classroom, 'publicId' | 'version'>): string {
  return `"${publicIdSchema.parse(classroom.publicId)}:v${z.number().int().positive().parse(classroom.version)}"`
}

export function classroomLayoutEtag(layout: { publicId: string; version: number }): string {
  return `"${publicIdSchema.parse(layout.publicId)}:v${z.number().int().positive().parse(layout.version)}"`
}

export const classroomAssignmentPlanEtag = classroomLayoutEtag
export const inPersonEventEtag = classroomLayoutEtag

export const classroomQueryKeys = {
  all: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'classrooms'] as const,
  list: (principal: PrincipalQueryScope, query: ClassroomListQuery = {}) => {
    const parsed = classroomListQuerySchema.parse(query)
    return [...classroomQueryKeys.all(principal), 'list', parsed.status, parsed.search] as const
  },
  events: (principal: PrincipalQueryScope) =>
    [...classroomQueryKeys.all(principal), 'events'] as const,
  layout: (principal: PrincipalQueryScope, eventPublicId: string) => [
    ...classroomQueryKeys.all(principal),
    'layout',
    publicIdSchema.parse(eventPublicId),
  ],
  assignmentPlan: (principal: PrincipalQueryScope, eventPublicId: string) => [
    ...classroomQueryKeys.all(principal),
    'assignment-plan',
    publicIdSchema.parse(eventPublicId),
  ],
  assignmentHistory: (
    principal: PrincipalQueryScope,
    eventPublicId: string,
    enrollmentPublicId: string,
  ) => [
    ...classroomQueryKeys.assignmentPlan(principal, eventPublicId),
    'history',
    publicIdSchema.parse(enrollmentPublicId),
  ],
  deliveryPreview: (principal: PrincipalQueryScope, planPublicId: string) => [
    ...classroomQueryKeys.all(principal),
    'delivery-preview',
    publicIdSchema.parse(planPublicId),
  ],
  deliveryBatch: (principal: PrincipalQueryScope, batchPublicId: string) => [
    ...classroomQueryKeys.all(principal),
    'delivery-batch',
    publicIdSchema.parse(batchPublicId),
  ],
  latestDelivery: (principal: PrincipalQueryScope, planPublicId: string) => [
    ...classroomQueryKeys.all(principal),
    'delivery-latest',
    publicIdSchema.parse(planPublicId),
  ],
  publishedAssignments: (principal: PrincipalQueryScope, studentPublicId?: string) => [
    ...classroomQueryKeys.all(principal),
    'published-assignments',
    studentPublicId === undefined ? 'self' : publicIdSchema.parse(studentPublicId),
  ],
} as const
