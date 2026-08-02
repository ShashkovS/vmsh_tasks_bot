import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

export const auditObjectTypeSchema = z.enum([
  'all',
  'account',
  'family_link',
  'course_enrollment',
  'problem_import',
  'course',
  'group',
  'telegram_binding',
  'problem_synonym',
  'staff_scope',
])
export type AuditObjectType = z.infer<typeof auditObjectTypeSchema>

const auditDiffValueSchema = z.union([z.string(), z.number(), z.boolean(), z.null()])
export const auditDiffSchema = z.record(z.string(), auditDiffValueSchema)
export type AuditDiff = z.infer<typeof auditDiffSchema>

export const auditEventSchema = z
  .object({
    eventId: publicIdSchema,
    occurredAt: z.iso.datetime(),
    audience: z.enum(['student', 'family', 'staff', 'system']),
    action: z.string().trim().min(1).max(128),
    objectType: auditObjectTypeSchema.exclude(['all']),
    objectId: z.string().trim().min(1).max(128),
    requestId: z.string().trim().min(1).max(128),
    actor: z
      .object({
        userId: publicIdSchema.nullable(),
        accountId: publicIdSchema.nullable(),
        displayName: z.string().trim().min(1).max(200),
      })
      .strict(),
    before: auditDiffSchema.nullable(),
    after: auditDiffSchema.nullable(),
  })
  .strict()
export type AuditEvent = z.infer<typeof auditEventSchema>

export const auditListResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    items: z.array(auditEventSchema),
    nextCursor: publicIdSchema.nullable(),
    requestId: z.string().trim().min(1).max(128),
  })
  .strict()
export type AuditListResponse = z.infer<typeof auditListResponseSchema>

export const auditQueryKeys = {
  list: (
    principal: PrincipalQueryScope,
    filter: { objectType: AuditObjectType; query: string; cursor: string | null },
  ) =>
    [
      'audit',
      ...principalQueryKey(principal),
      filter.objectType,
      filter.query,
      filter.cursor,
    ] as const,
} as const
