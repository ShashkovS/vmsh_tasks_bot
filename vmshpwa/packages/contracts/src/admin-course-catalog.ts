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
  .strip()
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
  .strip()
export type AdminCourse = z.infer<typeof adminCourseSchema>

export const courseVerdictModeSchema = z.enum([
  'verdict_plus_minus',
  'verdict_plus_minus_half',
  'verdict_plus_steps',
])
export type CourseVerdictMode = z.infer<typeof courseVerdictModeSchema>

export const courseRuntimeSettingsValuesSchema = z
  .object({
    verdictMode: courseVerdictModeSchema,
    resultMode: z.enum(['res_immed', 'res_after']),
    previousLessonsMode: z.enum([
      'prev_problems_hide',
      'prev_problems_prev',
      'prev_problems_show_all',
    ]),
    testAttemptRateLimit: z.enum(['rate_limit_none', 'rate_limit_3_and_6']),
  })
  .strip()
export type CourseRuntimeSettingsValues = z.infer<typeof courseRuntimeSettingsValuesSchema>

export const courseRuntimeSettingsSchema = z
  .object({
    courseId: publicIdSchema,
    values: courseRuntimeSettingsValuesSchema,
    version: z.number().int().nonnegative(),
    source: z.enum(['defaults', 'stored']),
    appliesAfter: z.literal('restart'),
  })
  .strip()

export const courseRuntimeSettingsResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    settings: courseRuntimeSettingsSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type CourseRuntimeSettingsResponse = z.infer<typeof courseRuntimeSettingsResponseSchema>

export const updateCourseRuntimeSettingsRequestSchema = z
  .object({ schemaVersion: z.literal(1), values: courseRuntimeSettingsValuesSchema })
  .strict()
export type UpdateCourseRuntimeSettingsRequest = z.infer<
  typeof updateCourseRuntimeSettingsRequestSchema
>

export const adminSeasonSchema = z
  .object({
    seasonId: publicIdSchema,
    code: z.string().trim().min(1),
    title: z.string().trim().min(1),
    status: catalogStatusSchema,
  })
  .strip()

export const adminCourseCatalogResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    season: adminSeasonSchema,
    courses: z.array(adminCourseSchema),
    requestId: z.string().trim().min(1),
  })
  .strip()
export type AdminCourseCatalogResponse = z.infer<typeof adminCourseCatalogResponseSchema>

export const createAdminSeasonRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    code: z.string().trim().min(1).max(30),
    title: z.string().trim().min(1).max(200),
    startsOn: z.iso.date(),
    endsOn: z.iso.date(),
    sessionExpiresOn: z.iso.date(),
    status: catalogStatusSchema,
  })
  .strict()
  .refine((value) => value.startsOn <= value.endsOn, { message: 'Invalid season dates' })
  .refine((value) => value.sessionExpiresOn >= value.endsOn, {
    message: 'Invalid session expiry',
  })
export type CreateAdminSeasonRequest = z.input<typeof createAdminSeasonRequestSchema>

export const adminSeasonResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    season: adminSeasonSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type AdminSeasonResponse = z.infer<typeof adminSeasonResponseSchema>

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
  .strip()
export type AdminCourseResponse = z.infer<typeof adminCourseResponseSchema>

export const adminGroupResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    group: adminGroupSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type AdminGroupResponse = z.infer<typeof adminGroupResponseSchema>

export const createAdminGroupLessonRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    lessonNumber: z.number().int().nonnegative().max(10_000),
    title: z.string().trim().min(1).max(200).nullable(),
    cycleAnchorDate: z.iso.date(),
    businessTimezone: z.string().trim().min(1).max(100),
    opensLocalTime: z.iso.datetime({ local: true, precision: -1 }).nullable(),
    submissionClosesLocalTime: z.iso.datetime({ local: true, precision: -1 }),
    hintScheduledLocalTime: z.iso.datetime({ local: true, precision: -1 }).nullable(),
    solutionScheduledLocalTime: z.iso.datetime({ local: true, precision: -1 }).nullable(),
  })
  .strict()
export type CreateAdminGroupLessonRequest = z.input<typeof createAdminGroupLessonRequestSchema>

export const adminGroupLessonSchema = z
  .object({
    groupLessonId: publicIdSchema,
    courseLessonId: publicIdSchema,
    courseId: publicIdSchema,
    groupId: publicIdSchema,
    lessonNumber: z.number().int().nonnegative().max(10_000),
    title: z.string().trim().min(1).max(200).nullable(),
    cycleAnchorDate: z.iso.date(),
    businessTimezone: z.string().trim().min(1).max(100),
    opensAt: z.iso.datetime({ offset: true }).nullable(),
    submissionClosesAt: z.iso.datetime({ offset: true }),
    hintScheduledAt: z.iso.datetime({ offset: true }).nullable(),
    solutionScheduledAt: z.iso.datetime({ offset: true }).nullable(),
  })
  .strip()

export const adminGroupLessonResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    groupLesson: adminGroupLessonSchema,
    requestId: z.string().trim().min(1),
  })
  .strip()
export type AdminGroupLessonResponse = z.infer<typeof adminGroupLessonResponseSchema>

export const adminCourseCatalogQueryKey = (principal: PrincipalQueryScope, seasonId?: string) =>
  [
    'admin-course-catalog',
    ...principalQueryKey(principal),
    { seasonId: seasonId === undefined ? null : publicIdSchema.parse(seasonId) },
  ] as const

export const courseRuntimeSettingsQueryKey = (
  principal: PrincipalQueryScope,
  rawCourseId: string,
) =>
  [
    'course-runtime-settings',
    ...principalQueryKey(principal),
    publicIdSchema.parse(rawCourseId),
  ] as const
