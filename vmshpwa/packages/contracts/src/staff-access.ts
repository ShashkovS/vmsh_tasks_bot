import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

const catalogStatusSchema = z.enum(['draft', 'active', 'archived'])

export const staffScopeSelectionSchema = z
  .object({
    courseId: publicIdSchema,
    groupId: publicIdSchema.nullable(),
  })
  .strict()
export type StaffScopeSelection = z.infer<typeof staffScopeSelectionSchema>

export const staffAccessScopeSchema = staffScopeSelectionSchema
  .extend({
    courseCode: z.string().trim().min(1),
    courseName: z.string().trim().min(1),
    courseStatus: catalogStatusSchema,
    groupCode: z.string().trim().min(1).nullable(),
    groupName: z.string().trim().min(1).nullable(),
    groupStatus: catalogStatusSchema.nullable(),
    version: z.number().int().positive(),
  })
  .strict()
  .superRefine((scope, context) => {
    const groupFields = [scope.groupCode, scope.groupName, scope.groupStatus]
    if (
      (scope.groupId === null && groupFields.some((value) => value !== null)) ||
      (scope.groupId !== null && groupFields.some((value) => value === null))
    ) {
      context.addIssue({ code: 'custom', message: 'Group metadata must match groupId' })
    }
  })
export type StaffAccessScope = z.infer<typeof staffAccessScopeSchema>

export const staffAccessMemberSchema = z
  .object({
    staffUserId: publicIdSchema,
    name: z.string().trim().min(1),
    surname: z.string().trim().min(1),
    middleName: z.string().nullable(),
    role: z.enum(['teacher', 'admin']),
    account: z
      .object({
        accountId: publicIdSchema,
        username: z.string().trim().min(1),
        status: z.enum(['active', 'blocked', 'disabled', 'archived']),
      })
      .strict()
      .nullable(),
    scopes: z.array(staffAccessScopeSchema),
  })
  .strict()
export type StaffAccessMember = z.infer<typeof staffAccessMemberSchema>

export const createStaffMemberRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    surname: z.string().trim().min(1).max(100),
    name: z.string().trim().min(1).max(100),
    middleName: z.string().trim().min(1).max(100).nullable(),
    username: z.string().trim().min(1).max(100),
    password: z.string().min(8).max(256),
  })
  .strict()
export type CreateStaffMemberRequest = z.infer<typeof createStaffMemberRequestSchema>

const staffMemberBatchRowSchema = createStaffMemberRequestSchema.omit({ schemaVersion: true })

export const createStaffMemberBatchRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    rows: z.array(staffMemberBatchRowSchema).min(1).max(500),
    scopes: z.array(staffScopeSelectionSchema).min(1).max(100),
  })
  .strict()
  .superRefine((request, context) => {
    const keys = request.scopes.map((scope) => `${scope.courseId}\0${scope.groupId ?? ''}`)
    if (new Set(keys).size !== keys.length) {
      context.addIssue({ code: 'custom', message: 'Scopes must be unique', path: ['scopes'] })
    }
    const courseWide = new Set(
      request.scopes.filter((scope) => scope.groupId === null).map((scope) => scope.courseId),
    )
    request.scopes.forEach((scope, index) => {
      if (scope.groupId !== null && courseWide.has(scope.courseId)) {
        context.addIssue({
          code: 'custom',
          message: 'Course-wide scope already includes its groups',
          path: ['scopes', index],
        })
      }
    })
  })
export type CreateStaffMemberBatchRequest = z.infer<typeof createStaffMemberBatchRequestSchema>

export const createStaffMemberBatchResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    counts: z
      .object({ total: z.number().int().positive(), created: z.number().int().positive() })
      .strict(),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type CreateStaffMemberBatchResponse = z.infer<typeof createStaffMemberBatchResponseSchema>

export const staffAccessDirectoryResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    members: z.array(staffAccessMemberSchema),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type StaffAccessDirectoryResponse = z.infer<typeof staffAccessDirectoryResponseSchema>

const expectedStaffScopeSchema = staffScopeSelectionSchema.extend({
  version: z.number().int().positive(),
})

export const replaceStaffScopesRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    expectedScopes: z.array(expectedStaffScopeSchema).max(100),
    scopes: z.array(staffScopeSelectionSchema).max(100),
  })
  .strict()
  .superRefine((request, context) => {
    for (const [field, scopes] of [
      ['expectedScopes', request.expectedScopes],
      ['scopes', request.scopes],
    ] as const) {
      const keys = scopes.map((scope) => `${scope.courseId}\0${scope.groupId ?? ''}`)
      if (new Set(keys).size !== keys.length) {
        context.addIssue({ code: 'custom', message: 'Scopes must be unique', path: [field] })
      }
    }
    const courseWide = new Set(
      request.scopes.filter((scope) => scope.groupId === null).map((scope) => scope.courseId),
    )
    request.scopes.forEach((scope, index) => {
      if (scope.groupId !== null && courseWide.has(scope.courseId)) {
        context.addIssue({
          code: 'custom',
          message: 'Course-wide scope already includes its groups',
          path: ['scopes', index],
        })
      }
    })
  })
export type ReplaceStaffScopesRequest = z.infer<typeof replaceStaffScopesRequestSchema>

export const staffAccessMemberResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    member: staffAccessMemberSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type StaffAccessMemberResponse = z.infer<typeof staffAccessMemberResponseSchema>

export const staffAccessQueryKey = (principal: PrincipalQueryScope) =>
  ['staff-access', ...principalQueryKey(principal)] as const
