import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'

export const managedAccountStatusSchema = z.enum(['active', 'blocked', 'disabled', 'archived'])
export type ManagedAccountStatus = z.infer<typeof managedAccountStatusSchema>
const groupStatusSchema = z.enum(['draft', 'active', 'archived'])
const attendanceModeSchema = z.enum(['online', 'in_person'])
const enrollmentStatusSchema = z.enum(['active', 'paused', 'archived'])

export const adminEnrollmentGroupSchema = z
  .object({
    groupId: publicIdSchema,
    code: z.string().trim().min(1).max(20),
    name: z.string().trim().min(1).max(100),
    status: groupStatusSchema,
    colorKey: z.string().trim().min(1).max(32),
    sortOrder: z.number().int(),
  })
  .strict()
export type AdminEnrollmentGroup = z.infer<typeof adminEnrollmentGroupSchema>

export const adminStudentCourseEnrollmentSchema = z
  .object({
    enrollmentId: publicIdSchema,
    course: z
      .object({
        courseId: publicIdSchema,
        code: z.string().trim().min(1).max(50),
        name: z.string().trim().min(1).max(200),
        subjectCode: z.string().trim().min(1).max(50),
      })
      .strict(),
    activeGroupId: publicIdSchema,
    allowedGroups: z.array(adminEnrollmentGroupSchema).min(1),
    attendanceMode: attendanceModeSchema,
    status: enrollmentStatusSchema,
    version: z.number().int().positive(),
  })
  .strict()
  .superRefine((enrollment, context) => {
    const groupIds = new Set<string>()
    enrollment.allowedGroups.forEach((group, index) => {
      if (groupIds.has(group.groupId)) {
        context.addIssue({
          code: 'custom',
          message: 'Allowed groups must be unique',
          path: ['allowedGroups', index, 'groupId'],
        })
      }
      groupIds.add(group.groupId)
    })
    if (!groupIds.has(enrollment.activeGroupId)) {
      context.addIssue({
        code: 'custom',
        message: 'Active group must be allowed',
        path: ['activeGroupId'],
      })
    }
  })
export type AdminStudentCourseEnrollment = z.infer<typeof adminStudentCourseEnrollmentSchema>

export const adminStudentDirectoryEntrySchema = z
  .object({
    studentId: publicIdSchema,
    surname: z.string().trim().min(1),
    name: z.string().trim().min(1),
    middleName: z.string().nullable(),
    grade: z.number().int().min(1).max(20).nullable(),
    birthday: z.iso.date().nullable(),
    strength: z.number().min(0).max(10).nullable(),
    webAccount: z
      .object({
        accountId: publicIdSchema,
        username: z.string().trim().min(1),
        status: managedAccountStatusSchema,
        credentialVersion: z.number().int().positive(),
      })
      .strict()
      .nullable(),
    familyAccounts: z.array(
      z
        .object({
          accountId: publicIdSchema,
          username: z.string().trim().min(1).max(100),
          displayName: z.string().trim().min(1),
          status: managedAccountStatusSchema,
          credentialVersion: z.number().int().positive(),
          relationshipLabel: z.string().trim().min(1),
          isPrimary: z.boolean(),
        })
        .strict(),
    ),
    enrollments: z.array(adminStudentCourseEnrollmentSchema),
  })
  .strict()
export type AdminStudentDirectoryEntry = z.infer<typeof adminStudentDirectoryEntrySchema>

export const adminStudentEnrollmentDirectoryResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    students: z.array(adminStudentDirectoryEntrySchema),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AdminStudentEnrollmentDirectoryResponse = z.infer<
  typeof adminStudentEnrollmentDirectoryResponseSchema
>

export const updateAdminStudentEnrollmentRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    activeGroupId: publicIdSchema,
    allowedGroupIds: z.array(publicIdSchema).min(1).max(100),
    attendanceMode: attendanceModeSchema,
    status: enrollmentStatusSchema,
  })
  .strict()
  .superRefine((request, context) => {
    const groupIds = new Set(request.allowedGroupIds)
    if (groupIds.size !== request.allowedGroupIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Allowed groups must be unique',
        path: ['allowedGroupIds'],
      })
    }
    if (!groupIds.has(request.activeGroupId)) {
      context.addIssue({
        code: 'custom',
        message: 'Active group must be allowed',
        path: ['activeGroupId'],
      })
    }
  })
export type UpdateAdminStudentEnrollmentRequest = z.infer<
  typeof updateAdminStudentEnrollmentRequestSchema
>

export const adminStudentEnrollmentResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    enrollment: adminStudentCourseEnrollmentSchema,
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AdminStudentEnrollmentResponse = z.infer<typeof adminStudentEnrollmentResponseSchema>

export const updateManagedAccountStatusRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    status: managedAccountStatusSchema,
  })
  .strict()
export type UpdateManagedAccountStatusRequest = z.infer<
  typeof updateManagedAccountStatusRequestSchema
>

export const replaceManagedAccountCredentialRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    credential: z.string().min(1).max(256),
  })
  .strict()
export type ReplaceManagedAccountCredentialRequest = z.infer<
  typeof replaceManagedAccountCredentialRequestSchema
>

export const managedAccountResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    account: z
      .object({
        accountId: publicIdSchema,
        audience: z.enum(['student', 'family']),
        status: managedAccountStatusSchema,
        credentialVersion: z.number().int().positive(),
      })
      .strict(),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type ManagedAccountResponse = z.infer<typeof managedAccountResponseSchema>

/** Family account/link boundary from development Phase 10; passwords are write-only. */
export const createFamilyAccountRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    username: z.string().trim().min(1).max(100),
    displayName: z.string().trim().min(1).max(200),
    password: z.string().min(8).max(256),
    relationshipLabel: z.string().trim().min(1).max(100),
    isPrimary: z.boolean(),
  })
  .strict()
export type CreateFamilyAccountRequest = z.infer<typeof createFamilyAccountRequestSchema>

export const linkFamilyAccountRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    familyUsername: z.string().trim().min(1).max(100),
    relationshipLabel: z.string().trim().min(1).max(100),
    isPrimary: z.boolean(),
  })
  .strict()
export type LinkFamilyAccountRequest = z.infer<typeof linkFamilyAccountRequestSchema>

export const familyAccountLinkResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    account: z
      .object({
        accountId: publicIdSchema,
        username: z.string().trim().min(1).max(100),
        displayName: z.string().trim().min(1).max(200),
        status: managedAccountStatusSchema,
        credentialVersion: z.number().int().positive(),
      })
      .strict(),
    link: z
      .object({
        studentId: publicIdSchema,
        relationshipLabel: z.string().trim().min(1).max(100),
        isPrimary: z.boolean(),
      })
      .strict(),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type FamilyAccountLinkResponse = z.infer<typeof familyAccountLinkResponseSchema>

export const unlinkFamilyAccountResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    studentId: publicIdSchema,
    accountId: publicIdSchema,
    revoked: z.literal(true),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type UnlinkFamilyAccountResponse = z.infer<typeof unlinkFamilyAccountResponseSchema>

export const adminStudentEnrollmentsQueryKey = (principal: PrincipalQueryScope) =>
  ['admin-student-enrollments', ...principalQueryKey(principal)] as const
