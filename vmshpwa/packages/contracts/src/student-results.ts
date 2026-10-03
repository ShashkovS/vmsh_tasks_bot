import { z } from 'zod'
import { publicIdSchema as id } from './auth'
import { webContentDocumentSchema } from './content'
import { reviewAnnotationManifestSchema } from './review-queue'

// vmshpwa/docs/student-results.md: read-only PWA + Telegram archive.
const envelope = { schemaVersion: z.literal(1), requestId: z.string() }
const student = z.object({
  studentId: id,
  name: z.string(),
  middleName: z.string().nullable(),
  grade: z.number().nullable(),
  groups: z.string(),
})
const current = z
  .object({
    verdict: z.number().int(),
    symbol: z.string(),
    author: z.string().nullable(),
    at: z.string(),
  })
  .nullable()
const attachment = z.object({
  id: z.string(),
  url: z.string().startsWith('/staff/api/v1/student-results/'),
  available: z.boolean(),
  kind: z.enum(['image', 'file']),
  annotation: reviewAnnotationManifestSchema.nullable(),
})
export const studentResultEventSchema = z.object({
  id: z.string(),
  kind: z.enum([
    'entry',
    'test',
    'review',
    'discussion',
    'result',
    'reaction',
    'student_reaction',
    'legacy_reaction',
    'transfer',
    'reassignment',
    'replacement',
    'undo',
  ]),
  at: z.string(),
  author: z.string().nullable(),
  authorKind: z.enum(['student', 'teacher', 'admin', 'ai', 'system']),
  source: z.string(),
  text: z.string().nullable(),
  verdict: z.number().int().nullable(),
  symbol: z.string(),
  revisionId: id.nullable(),
  attachments: z.array(attachment),
  reviewId: id.nullable(),
  internal: z.boolean(),
  action: z.string().nullable(),
  transfer: z
    .object({ mode: z.enum(['move', 'clone']), source: z.string(), target: z.string() })
    .nullable(),
  checkStatus: z.string().nullable(),
})
export const studentResultHistorySchema = z.object({
  events: z.array(studentResultEventSchema),
  nextCursor: z.string().nullable(),
  total: z.number().int(),
})
const problem = z.object({
  problemId: id,
  label: z.string(),
  title: z.string(),
  current,
  hasSubmissions: z.boolean(),
})
const group = z.object({
  groupId: id,
  name: z.string(),
  code: z.string(),
  problems: z.array(problem),
})
export const studentResultsDirectorySchema = z.object({ ...envelope, students: z.array(student) })
export const studentResultsOverviewSchema = z.object({
  ...envelope,
  student,
  courses: z.array(z.object({ courseId: id, name: z.string() })),
  courseId: id.nullable(),
  lessons: z.array(
    z.object({ number: z.number().int(), title: z.string(), hasActivity: z.boolean() }),
  ),
  summaries: z.array(z.object({ number: z.number().int(), groups: z.array(group) })),
})
export const studentResultsLessonSchema = z.object({
  ...envelope,
  number: z.number().int(),
  tables: z.array(group),
  groups: z.array(
    group.extend({
      problems: z.array(
        problem.extend({
          document: webContentDocumentSchema.nullable().catch(null),
          legacyCondition: z.string().nullable(),
          history: studentResultHistorySchema,
          reviewUrl: z.string().startsWith('/staff/review/').nullable(),
        }),
      ),
    }),
  ),
  notes: z.array(
    z.object({
      id: z.union([z.number(), z.string()]),
      action: z.enum(['current', 'changed', 'undo']),
      ts: z.string(),
      author: z.string(),
      reaction: z.string().nullable(),
      reaction_at: z.string().nullable(),
    }),
  ),
})
export const studentResultsConditionSchema = z.object({
  ...envelope,
  document: webContentDocumentSchema.nullable().catch(null),
})
export type StudentResultsOverview = z.infer<typeof studentResultsOverviewSchema>
export type StudentResultsLesson = z.infer<typeof studentResultsLessonSchema>
export type StudentResultHistory = z.infer<typeof studentResultHistorySchema>
export type StudentResultEvent = z.infer<typeof studentResultEventSchema>
