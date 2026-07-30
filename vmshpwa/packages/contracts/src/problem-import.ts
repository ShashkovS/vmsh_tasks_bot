import { z } from 'zod'

import { publicIdSchema } from './auth'

export const problemImportActionSchema = z.enum(['create', 'update', 'unchanged', 'invalid'])

export const problemImportDiagnosticSchema = z
  .object({
    sheet: z.enum(['Задачи', 'Старые']),
    row: z.number().int().positive(),
    field: z.string().min(1),
    code: z.string().min(1),
    message: z.string().min(1),
  })
  .strict()

export const problemImportRowSchema = z
  .object({
    sheet: z.enum(['Задачи', 'Старые']),
    row: z.number().int().positive(),
    groupCode: z.string().min(1).nullable(),
    groupId: publicIdSchema.nullable(),
    lessonNumber: z.number().int().nonnegative().nullable(),
    problemNumber: z.number().int().positive().nullable(),
    item: z.string(),
    title: z.string().min(1).nullable(),
    problemText: z.string(),
    problemType: z.number().int().min(1).max(4).nullable(),
    answerType: z.number().int().positive().nullable(),
    answerValidation: z.string().nullable(),
    validationError: z.string().nullable(),
    correctAnswer: z.string().nullable(),
    correctAnswerChecker: z.string().nullable(),
    wrongAnswer: z.string().nullable(),
    congratulation: z.string().nullable(),
    action: problemImportActionSchema,
    problemId: publicIdSchema.nullable(),
    diagnostics: z.array(problemImportDiagnosticSchema),
  })
  .strict()

export const problemImportSynonymCandidateSchema = z
  .object({
    lessonNumber: z.number().int().nonnegative(),
    normalizedTitle: z.string().min(1),
    displayTitle: z.string().min(1),
    hasGroupConflict: z.boolean(),
    members: z
      .array(
        z
          .object({
            sheet: z.enum(['Задачи', 'Старые']),
            row: z.number().int().positive(),
            groupCode: z.string().min(1),
            groupId: publicIdSchema,
            problemNumber: z.number().int().positive(),
            item: z.string(),
            problemId: publicIdSchema.nullable(),
            problemType: z.number().int().min(1).max(4),
            answerType: z.number().int().positive().nullable(),
          })
          .strict(),
      )
      .min(2),
  })
  .strict()

const problemImportSummarySchema = z
  .object({
    rows: z.number().int().nonnegative(),
    create: z.number().int().nonnegative(),
    update: z.number().int().nonnegative(),
    unchanged: z.number().int().nonnegative(),
    invalid: z.number().int().nonnegative(),
  })
  .strict()
  .superRefine((summary, context) => {
    if (summary.create + summary.update + summary.unchanged + summary.invalid !== summary.rows) {
      context.addIssue({ code: 'custom', message: 'Problem import summary does not add up' })
    }
  })

export const problemImportPreviewResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    course: z
      .object({
        courseId: publicIdSchema,
        code: z.string().min(1),
        name: z.string().min(1),
      })
      .strict(),
    source: z
      .object({
        filename: z.string().min(1),
        sha256: z.string().regex(/^[a-f0-9]{64}$/),
      })
      .strict(),
    previewSha256: z.string().regex(/^[a-f0-9]{64}$/),
    summary: problemImportSummarySchema,
    rows: z.array(problemImportRowSchema).max(5_000),
    synonymCandidates: z.array(problemImportSynonymCandidateSchema),
    requestId: z.string().min(1),
  })
  .strict()
  .superRefine((preview, context) => {
    if (preview.rows.length !== preview.summary.rows) {
      context.addIssue({ code: 'custom', message: 'Problem import row count does not match' })
    }
  })

const problemImportReceiptSummarySchema = z
  .object({
    rows: z.number().int().nonnegative(),
    created: z.number().int().nonnegative(),
    updated: z.number().int().nonnegative(),
    unchanged: z.number().int().nonnegative(),
    skippedInvalid: z.number().int().nonnegative(),
  })
  .strict()
  .superRefine((summary, context) => {
    if (
      summary.created + summary.updated + summary.unchanged + summary.skippedInvalid !==
      summary.rows
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Problem import receipt summary does not add up',
      })
    }
  })

export const problemImportReceiptSchema = z
  .object({
    schemaVersion: z.literal(1),
    importId: publicIdSchema,
    state: z.enum(['applied', 'rolled_back']),
    source: z
      .object({
        filename: z.string().min(1),
        sha256: z.string().regex(/^[a-f0-9]{64}$/),
      })
      .strict(),
    previewSha256: z.string().regex(/^[a-f0-9]{64}$/),
    summary: problemImportReceiptSummarySchema,
    appliedAt: z.iso.datetime({ offset: true }),
    rolledBackAt: z.iso.datetime({ offset: true }).nullable(),
    version: z.number().int().positive(),
    replayed: z.boolean(),
    requestId: z.string().min(1),
  })
  .strict()

export type ProblemImportAction = z.infer<typeof problemImportActionSchema>
export type ProblemImportPreviewResponse = z.infer<typeof problemImportPreviewResponseSchema>
export type ProblemImportReceipt = z.infer<typeof problemImportReceiptSchema>
export type ProblemImportRow = z.infer<typeof problemImportRowSchema>
export type ProblemImportSynonymCandidate = z.infer<typeof problemImportSynonymCandidateSchema>
