import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

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
  .strict()
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
  .strict()
export type ClassroomResponse = z.infer<typeof classroomResponseSchema>

export const classroomListResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    items: z.array(classroomSchema),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type ClassroomListResponse = z.infer<typeof classroomListResponseSchema>

export const inPersonEventStatusSchema = z.enum(['draft', 'scheduled', 'completed', 'cancelled'])
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
    lessonNumber: z.number().int().positive(),
    inPersonCount: z.number().int().nonnegative(),
    assignedCount: z.number().int().nonnegative(),
  })
  .strict()
export type ClassroomLayoutGroup = z.infer<typeof classroomLayoutGroupSchema>

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
  .strict()
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
      .strict(),
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
        .strict(),
    ),
  })
  .strict()
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
  .strict()
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
      .strict(),
    plan: z
      .object({
        publicId: publicIdSchema,
        state: classroomAssignmentPlanStateSchema,
        staleReason: z.string().nullable(),
        version: z.number().int().positive(),
        updatedAt: z.iso.datetime(),
        confirmedAt: z.iso.datetime().nullable(),
      })
      .strict()
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
        .strict(),
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
        .strict(),
    ),
  })
  .strict()
export type ClassroomAssignmentPlan = z.infer<typeof classroomAssignmentPlanSchema>

export const classroomAssignmentPlanResponseSchema = z
  .object({
    schemaVersion: classroomContractVersionSchema,
    assignmentPlan: classroomAssignmentPlanSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type ClassroomAssignmentPlanResponse = z.infer<typeof classroomAssignmentPlanResponseSchema>

export const recalculateClassroomAssignmentPlanRequestSchema =
  materializeClassroomLayoutRequestSchema
export type RecalculateClassroomAssignmentPlanRequest = z.infer<
  typeof recalculateClassroomAssignmentPlanRequestSchema
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

export const classroomQueryKeys = {
  all: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'classrooms'] as const,
  list: (principal: PrincipalQueryScope, query: ClassroomListQuery = {}) => {
    const parsed = classroomListQuerySchema.parse(query)
    return [...classroomQueryKeys.all(principal), 'list', parsed.status, parsed.search] as const
  },
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
} as const
