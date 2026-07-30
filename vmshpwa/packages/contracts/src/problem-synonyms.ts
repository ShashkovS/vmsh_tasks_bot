import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { answerTypeSchema, problemTypeSchema } from './content-api'

/**
 * Logical problem-synonym administration wire contract.
 * Concrete attempts, submissions and reviews remain owned by their original problem.
 * See `dev/development-plan/03-api-events-and-files.md` and
 * `apps/pwa_api/problem_synonym_routes.py`.
 */

export const problemSynonymProblemSchema = z
  .object({
    problemId: publicIdSchema,
    courseId: publicIdSchema,
    courseName: z.string().trim().min(1),
    courseLessonId: publicIdSchema,
    lessonNumber: z.number().int().nonnegative(),
    groupId: publicIdSchema,
    groupName: z.string().trim().min(1),
    groupCode: z.string().trim().min(1),
    groupLessonId: publicIdSchema,
    problemNumber: z.number().int().positive(),
    problemItem: z.string(),
    title: z.string().trim().min(1),
    problemType: problemTypeSchema,
    answerType: answerTypeSchema.nullable(),
    submissionCount: z.number().int().nonnegative(),
    reviewCount: z.number().int().nonnegative(),
    synonymId: publicIdSchema.nullable(),
  })
  .strict()

export const problemSynonymCandidateSchema = z
  .object({
    normalizedTitle: z.string().trim().min(1),
    displayTitle: z.string().trim().min(1),
    hasGroupConflict: z.boolean(),
    problems: z.array(problemSynonymProblemSchema).min(2).max(50),
  })
  .strict()

export const activeProblemSynonymGroupSchema = z
  .object({
    synonymId: publicIdSchema,
    displayTitle: z.string().trim().min(1),
    version: z.number().int().positive(),
    problems: z.array(problemSynonymProblemSchema).min(2).max(50),
  })
  .strict()

export const problemSynonymCandidatesResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    courseLessonId: publicIdSchema,
    candidates: z.array(problemSynonymCandidateSchema),
    synonymGroups: z.array(activeProblemSynonymGroupSchema),
    requestId: z.string().trim().min(1),
  })
  .strict()

export const problemSynonymImpactRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    mode: z.enum(['merge', 'split']),
    problemIds: z.array(publicIdSchema).min(1).max(50),
    synonymId: publicIdSchema.nullable(),
  })
  .strict()
  .superRefine((request, context) => {
    if (new Set(request.problemIds).size !== request.problemIds.length) {
      context.addIssue({ code: 'custom', message: 'Problem IDs must be unique' })
    }
    if (request.mode === 'merge' && request.problemIds.length < 2) {
      context.addIssue({ code: 'custom', message: 'Merge requires at least two problems' })
    }
    if (request.mode === 'merge' && request.synonymId !== null) {
      context.addIssue({ code: 'custom', message: 'Merge does not carry a synonym ID' })
    }
    if (request.mode === 'split' && request.synonymId === null) {
      context.addIssue({ code: 'custom', message: 'Split requires a synonym ID' })
    }
  })

export const problemSynonymMergeRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    problemIds: z.array(publicIdSchema).min(2).max(50),
    previewSha256: z.string().regex(/^[a-f0-9]{64}$/),
  })
  .strict()
  .refine((request) => new Set(request.problemIds).size === request.problemIds.length, {
    message: 'Problem IDs must be unique',
  })

export const problemSynonymSplitRequestSchema = z
  .object({
    schemaVersion: z.literal(1),
    problemIds: z.array(publicIdSchema).min(1).max(50),
    previewSha256: z.string().regex(/^[a-f0-9]{64}$/),
    reason: z.string().trim().min(1).max(500),
  })
  .strict()
  .refine((request) => new Set(request.problemIds).size === request.problemIds.length, {
    message: 'Problem IDs must be unique',
  })

const problemSynonymSummarySchema = z
  .object({
    synonymId: publicIdSchema,
    status: z.enum(['active', 'split', 'archived']),
    version: z.number().int().positive(),
  })
  .strict()

export const problemSynonymImpactResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    mode: z.enum(['merge', 'split']),
    synonym: problemSynonymSummarySchema.nullable(),
    problems: z.array(problemSynonymProblemSchema).min(1).max(50),
    selectedProblemIds: z.array(publicIdSchema).min(1).max(50),
    addProblemIds: z.array(publicIdSchema).max(50),
    removeProblemIds: z.array(publicIdSchema).max(50),
    submissionCount: z.number().int().nonnegative(),
    reviewCount: z.number().int().nonnegative(),
    previewSha256: z.string().regex(/^[a-f0-9]{64}$/),
    result: problemSynonymSummarySchema.extend({ changed: z.boolean() }).strict().optional(),
    requestId: z.string().trim().min(1),
  })
  .strict()

export type ProblemSynonymProblem = z.infer<typeof problemSynonymProblemSchema>
export type ProblemSynonymCandidate = z.infer<typeof problemSynonymCandidateSchema>
export type ActiveProblemSynonymGroup = z.infer<typeof activeProblemSynonymGroupSchema>
export type ProblemSynonymCandidatesResponse = z.infer<
  typeof problemSynonymCandidatesResponseSchema
>
export type ProblemSynonymImpactRequest = z.infer<typeof problemSynonymImpactRequestSchema>
export type ProblemSynonymMergeRequest = z.infer<typeof problemSynonymMergeRequestSchema>
export type ProblemSynonymSplitRequest = z.infer<typeof problemSynonymSplitRequestSchema>
export type ProblemSynonymImpactResponse = z.infer<typeof problemSynonymImpactResponseSchema>

export const problemSynonymQueryKeys = {
  all: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'problem-synonyms'] as const,
  lesson: (principal: PrincipalQueryScope, rawCourseLessonId: string) =>
    [
      ...problemSynonymQueryKeys.all(principal),
      'course-lesson',
      publicIdSchema.parse(rawCourseLessonId),
    ] as const,
} as const
