import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

export const oralWindowStateSchema = z.enum(['upcoming', 'open', 'closed', 'cancelled'])
export type OralWindowState = z.infer<typeof oralWindowStateSchema>

export const studentOralWindowSchema = z
  .object({
    windowId: publicIdSchema,
    sequenceNumber: z.number().int().positive(),
    opensAt: z.iso.datetime(),
    closesAt: z.iso.datetime(),
    joinLabel: z.string().trim().min(1).max(200),
    state: oralWindowStateSchema,
    joinAvailable: z.boolean(),
    version: z.number().int().positive(),
  })
  .strip()
export type StudentOralWindow = z.infer<typeof studentOralWindowSchema>

export const studentOralWindowListResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(studentOralWindowSchema),
    requestId: z.string().min(1),
  })
  .strip()
export type StudentOralWindowListResponse = z.infer<typeof studentOralWindowListResponseSchema>

export const oralWindowJoinSchema = z
  .object({
    windowId: publicIdSchema,
    joinLabel: z.string().trim().min(1).max(200),
    joinUrl: z.url().startsWith('https://'),
    joinCode: z.string().trim().min(1).nullable(),
    closesAt: z.iso.datetime(),
  })
  .strip()
export type OralWindowJoin = z.infer<typeof oralWindowJoinSchema>

export const oralWindowJoinResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    join: oralWindowJoinSchema,
    requestId: z.string().min(1),
  })
  .strip()
export type OralWindowJoinResponse = z.infer<typeof oralWindowJoinResponseSchema>

export const oralWindowQueryKeys = {
  student: (principal: PrincipalQueryScope, courseId: string, groupLessonId: string) =>
    [
      'oral-windows',
      'student',
      ...principalQueryKey(principal),
      publicIdSchema.parse(courseId),
      publicIdSchema.parse(groupLessonId),
    ] as const,
}
