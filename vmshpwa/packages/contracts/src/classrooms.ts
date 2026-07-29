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

export function classroomEtag(classroom: Pick<Classroom, 'publicId' | 'version'>): string {
  return `"${publicIdSchema.parse(classroom.publicId)}:v${z.number().int().positive().parse(classroom.version)}"`
}

export const classroomQueryKeys = {
  all: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'classrooms'] as const,
  list: (principal: PrincipalQueryScope, query: ClassroomListQuery = {}) => {
    const parsed = classroomListQuerySchema.parse(query)
    return [...classroomQueryKeys.all(principal), 'list', parsed.status, parsed.search] as const
  },
} as const
