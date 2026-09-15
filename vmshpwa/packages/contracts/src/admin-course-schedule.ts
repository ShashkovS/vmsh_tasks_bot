import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const requestIdSchema = z.string().trim().min(1)

export const scheduleFieldSchema = z.enum([
  'opens_at',
  'hint_scheduled_at',
  'submission_closes_at',
  'solution_scheduled_at',
])
export const scheduleStateSchema = z.enum(['draft', 'active'])
export const scheduleOverrideModeSchema = z.enum(['inherit', 'override', 'disabled'])
const localTimeSchema = z.string().regex(/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/)
const timezoneSchema = z.string().trim().min(1).max(64)

export const adminCourseScheduleRuleSchema = z
  .object({
    ruleId: publicIdSchema,
    field: scheduleFieldSchema,
    ruleVersion: z.number().int().positive(),
    dayOffset: z.number().int().min(-30).max(30),
    localTime: localTimeSchema,
    timezone: timezoneSchema,
    state: scheduleStateSchema,
    version: z.number().int().positive(),
  })
  .strip()

export const adminCourseScheduleResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    courseId: publicIdSchema,
    rules: z.array(adminCourseScheduleRuleSchema).max(8),
    draftImpacts: z
      .array(
        z
          .object({
            ruleId: publicIdSchema,
            groupLessons: z.number().int().nonnegative(),
            materializedWindows: z.number().int().nonnegative(),
          })
          .strip(),
      )
      .max(4),
    requestId: requestIdSchema,
  })
  .strip()

export const saveAdminCourseScheduleRuleSchema = z
  .object({
    schemaVersion: z.literal(1),
    field: scheduleFieldSchema,
    dayOffset: z.number().int().min(-30).max(30),
    localTime: localTimeSchema,
    timezone: timezoneSchema,
  })
  .strict()

export const adminCourseScheduleDraftResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    rule: adminCourseScheduleRuleSchema,
    impact: z
      .object({
        groupLessons: z.number().int().nonnegative(),
        materializedWindows: z.number().int().nonnegative(),
      })
      .strip(),
    requestId: requestIdSchema,
  })
  .strip()

export const adminCourseScheduleRuleResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    rule: adminCourseScheduleRuleSchema,
    requestId: requestIdSchema,
  })
  .strip()

export const adminGroupScheduleOverrideSchema = z
  .object({
    overrideId: publicIdSchema,
    field: scheduleFieldSchema,
    overrideVersion: z.number().int().positive(),
    mode: scheduleOverrideModeSchema,
    dayOffset: z.number().int().min(-30).max(30).nullable(),
    localTime: localTimeSchema.nullable(),
    timezone: timezoneSchema.nullable(),
    baseRuleId: z.number().int().positive(),
    state: scheduleStateSchema,
    version: z.number().int().positive(),
  })
  .strip()

export const adminGroupScheduleResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    groupId: publicIdSchema,
    courseRules: z.array(adminCourseScheduleRuleSchema).max(8),
    overrides: z.array(adminGroupScheduleOverrideSchema).max(8),
    requestId: requestIdSchema,
  })
  .strip()

export const saveAdminGroupScheduleOverrideSchema = z
  .object({
    schemaVersion: z.literal(1),
    field: scheduleFieldSchema,
    mode: scheduleOverrideModeSchema,
    dayOffset: z.number().int().min(-30).max(30).nullable(),
    localTime: localTimeSchema.nullable(),
    timezone: timezoneSchema.nullable(),
  })
  .strict()
  .superRefine((value, context) => {
    const hasValue = value.dayOffset !== null && value.localTime !== null && value.timezone !== null
    if (value.mode === 'override' && !hasValue) {
      context.addIssue({ code: 'custom', message: 'Override requires a complete value' })
    }
    if (
      value.mode !== 'override' &&
      (value.dayOffset !== null || value.localTime !== null || value.timezone !== null)
    ) {
      context.addIssue({ code: 'custom', message: 'Inherited or disabled fields have no value' })
    }
    if (value.field === 'submission_closes_at' && value.mode === 'disabled') {
      context.addIssue({ code: 'custom', message: 'Submission cutoff cannot be disabled' })
    }
  })

export const adminGroupScheduleOverrideResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    override: adminGroupScheduleOverrideSchema,
    requestId: requestIdSchema,
  })
  .strip()

export type ScheduleField = z.infer<typeof scheduleFieldSchema>
export type ScheduleOverrideMode = z.infer<typeof scheduleOverrideModeSchema>
export type AdminCourseScheduleRule = z.infer<typeof adminCourseScheduleRuleSchema>
export type AdminCourseScheduleResponse = z.infer<typeof adminCourseScheduleResponseSchema>
export type SaveAdminCourseScheduleRule = z.infer<typeof saveAdminCourseScheduleRuleSchema>
export type AdminCourseScheduleDraftResponse = z.infer<
  typeof adminCourseScheduleDraftResponseSchema
>
export type AdminCourseScheduleRuleResponse = z.infer<typeof adminCourseScheduleRuleResponseSchema>
export type AdminGroupScheduleOverride = z.infer<typeof adminGroupScheduleOverrideSchema>
export type AdminGroupScheduleResponse = z.infer<typeof adminGroupScheduleResponseSchema>
export type SaveAdminGroupScheduleOverride = z.infer<typeof saveAdminGroupScheduleOverrideSchema>
export type AdminGroupScheduleOverrideResponse = z.infer<
  typeof adminGroupScheduleOverrideResponseSchema
>

export function adminCourseScheduleQueryKey(scope: PrincipalQueryScope, rawCourseId: string) {
  const courseId = publicIdSchema.parse(rawCourseId)
  return ['admin-course-schedule', ...principalQueryKey(scope), courseId] as const
}

export function adminGroupScheduleQueryKey(scope: PrincipalQueryScope, rawGroupId: string) {
  const groupId = publicIdSchema.parse(rawGroupId)
  return ['admin-group-schedule', ...principalQueryKey(scope), groupId] as const
}
