import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

/** Phase-6 private Student/Staff support-thread wire contract. */
export const SUPPORT_CONTRACT_VERSION = 1 as const
const supportContractVersionSchema = z.literal(SUPPORT_CONTRACT_VERSION)
const supportTextSchema = z
  .string()
  .min(1)
  .max(100_000)
  .refine((value) => value.trim().length > 0)
const idempotencyKeySchema = z.string().trim().min(1).max(200)

export const supportThreadKindSchema = z.enum(['problem_question', 'general', 'sos'])
export type SupportThreadKind = z.infer<typeof supportThreadKindSchema>

export const createSupportThreadRequestSchema = z
  .object({
    schemaVersion: supportContractVersionSchema,
    idempotencyKey: idempotencyKeySchema,
    kind: z.enum(['problem_question', 'general']),
    groupLessonId: publicIdSchema,
    problemId: publicIdSchema.nullable(),
    text: supportTextSchema,
    clientCreatedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((request, context) => {
    if (request.kind === 'problem_question' && request.problemId === null) {
      context.addIssue({
        code: 'custom',
        message: 'Problem question requires a problem',
        path: ['problemId'],
      })
    }
    if (request.kind === 'general' && request.problemId !== null) {
      context.addIssue({
        code: 'custom',
        message: 'General question cannot reference a problem',
        path: ['problemId'],
      })
    }
  })
export type CreateSupportThreadRequest = z.infer<typeof createSupportThreadRequestSchema>

export const appendSupportEntryRequestSchema = z
  .object({
    schemaVersion: supportContractVersionSchema,
    idempotencyKey: idempotencyKeySchema,
    text: supportTextSchema,
    clientCreatedAt: z.iso.datetime(),
  })
  .strict()
export type AppendSupportEntryRequest = z.infer<typeof appendSupportEntryRequestSchema>

export const supportEntrySchema = z
  .object({
    entryId: publicIdSchema,
    author: z
      .object({
        kind: z.enum(['student', 'teacher', 'admin', 'system']),
        userId: publicIdSchema.nullable(),
        displayName: z.string().trim().min(1).max(200),
      })
      .strict(),
    text: z.string().max(100_000).nullable(),
    assetId: publicIdSchema.nullable(),
    channel: z.enum(['pwa', 'telegram', 'staff', 'system']),
    clientCreatedAt: z.iso.datetime().nullable(),
    receivedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((entry, context) => {
    if ((entry.author.kind === 'system') !== (entry.author.userId === null)) {
      context.addIssue({
        code: 'custom',
        message: 'Only system entries omit the author identity',
        path: ['author', 'userId'],
      })
    }
    if (entry.text === null && entry.assetId === null) {
      context.addIssue({
        code: 'custom',
        message: 'Support entry must contain text or an asset',
        path: ['text'],
      })
    }
  })
export type SupportEntry = z.infer<typeof supportEntrySchema>

export const supportThreadSchema = z
  .object({
    threadId: publicIdSchema,
    kind: supportThreadKindSchema,
    student: z
      .object({
        studentId: publicIdSchema,
        displayName: z.string().trim().min(1).max(200),
      })
      .strict(),
    context: z
      .object({
        courseId: publicIdSchema.nullable(),
        courseName: z.string().trim().min(1).max(200).nullable(),
        groupId: publicIdSchema.nullable(),
        groupName: z.string().trim().min(1).max(200).nullable(),
        groupLessonId: publicIdSchema.nullable(),
        problemId: publicIdSchema.nullable(),
        problemTitle: z.string().trim().min(1).max(500).nullable(),
      })
      .strict(),
    latestEntryAt: z.iso.datetime(),
    version: z.number().int().positive(),
    entries: z.array(supportEntrySchema).min(1),
  })
  .strict()
  .superRefine((thread, context) => {
    const problemContext = thread.context.problemId !== null && thread.context.problemTitle !== null
    if (thread.kind === 'problem_question' && !problemContext) {
      context.addIssue({
        code: 'custom',
        message: 'Problem question requires complete problem context',
        path: ['context', 'problemId'],
      })
    }
    if (
      thread.kind !== 'problem_question' &&
      (thread.context.problemId !== null || thread.context.problemTitle !== null)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Non-problem thread cannot expose problem context',
        path: ['context', 'problemId'],
      })
    }
    for (let index = 1; index < thread.entries.length; index += 1) {
      const previous = thread.entries[index - 1]
      const current = thread.entries[index]
      if (previous && current && current.receivedAt < previous.receivedAt) {
        context.addIssue({
          code: 'custom',
          message: 'Support entries must be chronological',
          path: ['entries', index, 'receivedAt'],
        })
      }
    }
    if (thread.entries.at(-1)?.receivedAt !== thread.latestEntryAt) {
      context.addIssue({
        code: 'custom',
        message: 'Latest entry timestamp must match the chronological tail',
        path: ['latestEntryAt'],
      })
    }
  })
export type SupportThread = z.infer<typeof supportThreadSchema>

export const supportThreadResponseSchema = z
  .object({
    schemaVersion: supportContractVersionSchema,
    thread: supportThreadSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type SupportThreadResponse = z.infer<typeof supportThreadResponseSchema>

export const supportQueryKeys = {
  all: (principal: PrincipalQueryScope) => [...principalQueryKey(principal), 'support'] as const,
  thread: (principal: PrincipalQueryScope, threadId: string) =>
    [...supportQueryKeys.all(principal), 'thread', publicIdSchema.parse(threadId)] as const,
} as const
