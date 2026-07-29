import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

export const catalogStatusSchema = z.enum(['draft', 'active', 'archived'])
export type CatalogStatus = z.infer<typeof catalogStatusSchema>

export const adminGroupSchema = z
  .object({
    groupId: publicIdSchema,
    shortCode: z.string().trim().min(1).max(20),
    name: z.string().trim().min(1).max(100),
    status: catalogStatusSchema,
    colorKey: z.string().trim().min(1).max(32).nullable(),
    sortOrder: z.number().int().min(-10_000).max(10_000),
    allowSelfSwitch: z.boolean(),
    isDefault: z.boolean(),
    isSystem: z.boolean(),
    scoreWeight: z.number().positive().max(10),
    activeStudents: z.number().int().nonnegative(),
    version: z.number().int().positive(),
  })
  .strict()
export type AdminGroup = z.infer<typeof adminGroupSchema>

export const adminCourseSchema = z
  .object({
    courseId: publicIdSchema,
    code: z.string().trim().min(1).max(20),
    name: z.string().trim().min(1).max(200),
    subjectCode: z.string().trim().min(1).max(50),
    status: catalogStatusSchema,
    sortOrder: z.number().int().min(-10_000).max(10_000),
    accentKey: z.string().trim().min(1).max(32),
    activeStudents: z.number().int().nonnegative(),
    groups: z.array(adminGroupSchema),
    version: z.number().int().positive(),
  })
  .strict()
export type AdminCourse = z.infer<typeof adminCourseSchema>

const seasonSchema = z
  .object({
    seasonId: publicIdSchema,
    code: z.string().trim().min(1),
    title: z.string().trim().min(1),
    status: catalogStatusSchema,
  })
  .strict()

export const adminCourseCatalogResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    season: seasonSchema,
    courses: z.array(adminCourseSchema),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AdminCourseCatalogResponse = z.infer<typeof adminCourseCatalogResponseSchema>

const codeSchema = z
  .string()
  .trim()
  .min(1)
  .max(50)
  .transform((value) => value.toLocaleLowerCase('ru-RU'))

const courseFields = {
  schemaVersion: z.literal(1),
  code: codeSchema,
  name: z.string().trim().min(1).max(200),
  subjectCode: codeSchema,
  status: catalogStatusSchema,
  sortOrder: z.number().int().min(-10_000).max(10_000),
  accentKey: z.string().trim().min(1).max(32),
}

export const createAdminCourseRequestSchema = z
  .object({ ...courseFields, seasonId: publicIdSchema })
  .strict()
export type CreateAdminCourseRequest = z.input<typeof createAdminCourseRequestSchema>

export const updateAdminCourseRequestSchema = z.object(courseFields).strict()
export type UpdateAdminCourseRequest = z.input<typeof updateAdminCourseRequestSchema>

export const saveAdminGroupRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    shortCode: codeSchema,
    name: z.string().trim().min(1).max(100),
    status: catalogStatusSchema,
    colorKey: z.string().trim().min(1).max(32),
    sortOrder: z.number().int().min(-10_000).max(10_000),
    allowSelfSwitch: z.boolean(),
    scoreWeight: z.number().positive().max(10),
  })
  .strict()
export type SaveAdminGroupRequest = z.input<typeof saveAdminGroupRequestSchema>

export const adminCourseResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    course: adminCourseSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AdminCourseResponse = z.infer<typeof adminCourseResponseSchema>

export const adminGroupResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    group: adminGroupSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AdminGroupResponse = z.infer<typeof adminGroupResponseSchema>

export const adminCourseCatalogQueryKey = (principal: PrincipalQueryScope, seasonId?: string) =>
  [
    'admin-course-catalog',
    ...principalQueryKey(principal),
    { seasonId: seasonId === undefined ? null : publicIdSchema.parse(seasonId) },
  ] as const
