import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

export const oralResultOutcomeSchema = z.enum(['accepted', 'rejected'])
export type OralResultOutcome = z.infer<typeof oralResultOutcomeSchema>

export const staffOralRosterResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    groupLessonId: publicIdSchema,
    students: z.array(
      z
        .object({
          studentId: publicIdSchema,
          displayName: z.string().trim().min(1),
        })
        .strip(),
    ),
    problems: z.array(
      z
        .object({
          problemId: publicIdSchema,
          displayNumber: z.string().trim().min(1),
          title: z.string().trim().min(1),
        })
        .strip(),
    ),
    requestId: z.string().min(1),
  })
  .strip()
export type StaffOralRosterResponse = z.infer<typeof staffOralRosterResponseSchema>

export const recordOralResultRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    studentId: publicIdSchema,
    idempotencyKey: publicIdSchema,
    marks: z
      .array(
        z
          .object({
            problemId: publicIdSchema,
            outcome: oralResultOutcomeSchema,
          })
          .strict(),
      )
      .min(1)
      .max(50),
    reactionId: z
      .union([z.literal(300), z.literal(301), z.literal(302), z.literal(303)])
      .nullable(),
  })
  .strict()
export type RecordOralResultRequest = z.infer<typeof recordOralResultRequestSchema>

export const recordOralResultResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    idempotencyKey: publicIdSchema,
    replayed: z.boolean(),
    marks: z.array(
      z
        .object({
          problemId: publicIdSchema,
          outcome: oralResultOutcomeSchema,
        })
        .strip(),
    ),
    reactionId: z.number().int().nullable(),
    requestId: z.string().min(1),
  })
  .strip()
export type RecordOralResultResponse = z.infer<typeof recordOralResultResponseSchema>

export const oralResultQueryKeys = {
  staffRoster: (principal: PrincipalQueryScope, groupLessonId: string) =>
    [
      'oral-results',
      'staff-roster',
      ...principalQueryKey(principal),
      publicIdSchema.parse(groupLessonId),
    ] as const,
}
