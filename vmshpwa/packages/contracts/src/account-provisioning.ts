import { z } from 'zod'

import { publicIdSchema } from './auth'

/** Phase-1/10 v1 batch boundary; credentials are write-only. */
export const studentProvisioningRowSchema = z
  .object({
    surname: z.string().trim().min(1).max(100),
    name: z.string().trim().min(1).max(100),
    patronymic: z.string().max(100).optional(),
    birthDate: z.iso.date().nullable().optional(),
    grade: z.number().int().min(1).max(11).nullable().optional(),
    login: z.string().trim().min(1).max(100),
    password: z.string().min(1).max(256),
  })
  .strict()
export type StudentProvisioningRow = z.infer<typeof studentProvisioningRowSchema>

export const familyProvisioningRowSchema = z
  .object({
    name: z.string().trim().min(1).max(200),
    login: z.string().trim().min(1).max(100),
    password: z.string().min(1).max(256),
    emails: z.union([
      z.string().trim().min(1).max(2_000),
      z.array(z.email().max(320)).min(1).max(20),
    ]),
    childLogins: z.array(z.string().trim().min(1).max(100)).min(1).max(20),
  })
  .strict()
export type FamilyProvisioningRow = z.infer<typeof familyProvisioningRowSchema>

function previewRequest<Row extends z.ZodType>(row: Row) {
  return z.object({ schemaVersion: z.literal(1), rows: z.array(row).min(1).max(2_000) }).strict()
}

export const studentProvisioningPreviewRequestSchema = previewRequest(studentProvisioningRowSchema)
export type StudentProvisioningPreviewRequest = z.infer<
  typeof studentProvisioningPreviewRequestSchema
>
export const familyProvisioningPreviewRequestSchema = previewRequest(familyProvisioningRowSchema)
export type FamilyProvisioningPreviewRequest = z.infer<
  typeof familyProvisioningPreviewRequestSchema
>

const readyPreviewRowSchema = z
  .object({
    rowNumber: z.number().int().positive(),
    state: z.literal('ready'),
    resolvedLogin: z.string().trim().min(1).max(100),
    loginAdjusted: z.boolean(),
    code: z.null(),
  })
  .strict()
const invalidPreviewRowSchema = z
  .object({
    rowNumber: z.number().int().positive(),
    state: z.literal('invalid'),
    resolvedLogin: z.null(),
    loginAdjusted: z.literal(false),
    code: z.string().trim().min(1).max(100),
  })
  .strict()
export const accountProvisioningPreviewRowSchema = z.discriminatedUnion('state', [
  readyPreviewRowSchema,
  invalidPreviewRowSchema,
])
export type AccountProvisioningPreviewRow = z.infer<typeof accountProvisioningPreviewRowSchema>

export const accountProvisioningPreviewResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    previewHash: z.string().regex(/^[a-f0-9]{64}$/),
    counts: z
      .object({
        total: z.number().int().positive(),
        ready: z.number().int().nonnegative(),
        invalid: z.number().int().nonnegative(),
      })
      .strict(),
    rows: z.array(accountProvisioningPreviewRowSchema).min(1).max(2_000),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AccountProvisioningPreviewResponse = z.infer<
  typeof accountProvisioningPreviewResponseSchema
>

function applyRequest<Row extends z.ZodType>(row: Row) {
  return z
    .object({
      schemaVersion: z.literal(1),
      rows: z.array(row).min(1).max(2_000),
      resolvedLogins: z.array(z.string().trim().min(1).max(100).nullable()).min(1).max(2_000),
      previewHash: z.string().regex(/^[a-f0-9]{64}$/),
    })
    .strict()
    .superRefine((request, context) => {
      if (request.rows.length !== request.resolvedLogins.length) {
        context.addIssue({
          code: 'custom',
          message: 'Resolved logins must match batch rows',
          path: ['resolvedLogins'],
        })
      }
    })
}

export const studentProvisioningApplyRequestSchema = applyRequest(studentProvisioningRowSchema)
export type StudentProvisioningApplyRequest = z.infer<typeof studentProvisioningApplyRequestSchema>
export const familyProvisioningApplyRequestSchema = applyRequest(familyProvisioningRowSchema)
export type FamilyProvisioningApplyRequest = z.infer<typeof familyProvisioningApplyRequestSchema>

const createdReceiptRowSchema = z
  .object({
    rowNumber: z.number().int().positive(),
    state: z.literal('created'),
    login: z.string().trim().min(1).max(100),
    accountId: publicIdSchema,
    userId: publicIdSchema.optional(),
    childCount: z.number().int().positive().optional(),
  })
  .strict()
const skippedReceiptRowSchema = z
  .object({
    rowNumber: z.number().int().positive(),
    state: z.literal('skipped'),
    code: z.string().trim().min(1).max(100),
  })
  .strict()
export const accountProvisioningReceiptRowSchema = z.discriminatedUnion('state', [
  createdReceiptRowSchema,
  skippedReceiptRowSchema,
])
export const accountProvisioningReceiptSchema = z
  .object({
    schemaVersion: z.literal(1),
    counts: z
      .object({
        total: z.number().int().positive(),
        created: z.number().int().nonnegative(),
        skipped: z.number().int().nonnegative(),
      })
      .strict(),
    rows: z.array(accountProvisioningReceiptRowSchema).min(1).max(2_000),
    requestId: z.string().trim().min(1),
  })
  .strict()
export type AccountProvisioningReceipt = z.infer<typeof accountProvisioningReceiptSchema>
