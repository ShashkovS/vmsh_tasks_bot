import { z } from 'zod'
import { publicIdSchema } from './auth'

// vmshpwa/docs/live-marking.md; shared by both Staff workspaces and the outbox.
const id = publicIdSchema
const version = z.number().int().nonnegative()
const envelope = { schemaVersion: z.literal(1), requestId: z.string() }
export const liveContextSchema = z
  .object({
    mode: z.enum(['school', 'zoom']),
    contextId: id,
    roomId: id.optional(),
    lessonId: id.optional(),
    studentId: id.optional(),
  })
  .strict()
export type LiveContext = z.infer<typeof liveContextSchema>
const base = { operationId: id, context: liveContextSchema }
export const liveCommandSchema = z.discriminatedUnion('kind', [
  z
    .object({
      ...base,
      kind: z.literal('mark'),
      studentId: id,
      problemId: id,
      expectedVersion: version,
      value: z.enum(['plus', 'minus']),
    })
    .strict(),
  z
    .object({
      ...base,
      kind: z.literal('attendance'),
      studentId: id,
      expectedVersion: version,
      value: z.enum(['unmarked', 'present', 'absent']),
    })
    .strict(),
  z
    .object({
      ...base,
      kind: z.literal('transfer'),
      studentId: id,
      enrollmentVersion: version,
      planId: id,
    })
    .strict(),
  z
    .object({
      ...base,
      kind: z.literal('reaction'),
      studentId: id,
      expectedVersion: version,
      reactions: z
        .array(
          z.union([z.literal(300), z.literal(301), z.literal(303), z.literal(304), z.literal(305)]),
        )
        .max(5),
    })
    .strict(),
  z
    .object({ ...base, kind: z.literal('praise'), studentId: id, expectedVersion: version })
    .strict(),
  z.object({ ...base, kind: z.literal('undo'), targetOperationId: id }).strict(),
])
export type LiveCommand = z.infer<typeof liveCommandSchema>
export const liveCellSchema = z.object({
  studentId: id,
  problemId: id,
  version,
  verdict: z.number().int().nullable(),
  symbol: z.string(),
  teacherId: id.nullable(),
  updatedAt: z.string().nullable(),
})
export type LiveCell = z.infer<typeof liveCellSchema>
export const liveCellsSchema = z.object({
  ...envelope,
  cells: z.array(liveCellSchema),
  cursor: version,
  scope: z.string(),
  reset: z.boolean(),
})
export type LiveCells = z.infer<typeof liveCellsSchema>
export const liveLessonSchema = z.object({
  lessonId: id,
  number: z.number().int(),
  groupId: id,
  groupName: z.string(),
})
const sessionSchema = z.object({
  sessionId: id,
  createdAt: z.string(),
  finishedAt: z.string().nullable(),
})
export const liveCatalogSchema = z.object({
  ...envelope,
  courses: z.array(
    z.object({
      courseId: id,
      name: z.string(),
      lessons: z.array(liveLessonSchema),
      sessions: z.array(sessionSchema),
    }),
  ),
  events: z.array(
    z.object({
      eventId: id,
      name: z.string(),
      startsAt: z.string(),
      status: z.string(),
      rooms: z.array(
        z.object({
          roomId: id,
          name: z.string(),
          courseId: id,
          groupId: id,
          groupName: z.string(),
          lessonId: id,
        }),
      ),
    }),
  ),
})
export type LiveCatalog = z.infer<typeof liveCatalogSchema>
const studentSchema = z.object({
  studentId: id,
  displayName: z.string(),
  middleName: z.string().nullable(),
  grade: z.union([z.number(), z.string()]).nullable(),
  groupId: id,
  groupName: z.string(),
  attendanceMode: z.enum(['online', 'in_person']),
  enrollmentVersion: version,
})
export const liveDirectorySchema = z.object({
  ...envelope,
  students: z.array(
    studentSchema.extend({
      rooms: z.array(
        z.object({
          eventId: id,
          eventName: z.string(),
          startsAt: z.string(),
          roomName: z.string().nullable(),
        }),
      ),
    }),
  ),
})
export type LiveDirectoryStudent = z.infer<typeof liveDirectorySchema>['students'][number]
export const liveVisitSchema = z.object({
  version,
  reactions: z.array(z.number().int()),
  praisedAt: z.string().nullable(),
})
export const liveBoardSchema = z.object({
  ...envelope,
  lesson: liveLessonSchema,
  students: z.array(
    studentSchema.extend({
      attendance: z.enum(['unmarked', 'present', 'absent']),
      attendanceVersion: version,
    }),
  ),
  problems: z.array(
    z.object({
      problemId: id,
      label: z.string(),
      title: z.string(),
      oral: z.boolean(),
      number: z.number().int(),
    }),
  ),
  planId: id.nullable(),
  readOnly: z.boolean(),
  visit: liveVisitSchema.nullable(),
})
export type LiveBoard = z.infer<typeof liveBoardSchema>
export const liveStateSchema = z.object({
  kind: z.enum(['mark', 'attendance', 'transfer', 'reaction', 'praise', 'undo']),
  studentId: id,
  version: z.union([version, z.string()]),
  lessonId: id.optional(),
  problemId: id.optional(),
  verdict: z.number().nullable().optional(),
  symbol: z.string().optional(),
  teacherId: id.nullable().optional(),
  updatedAt: z.string().nullable().optional(),
  value: z.string().optional(),
  reactions: z.array(z.number()).optional(),
  praisedAt: z.string().nullable().optional(),
  targetOperationId: id.optional(),
  objectKey: z.string().optional(),
})
export const liveReceiptSchema = z.object({
  ...envelope,
  operationId: id,
  replayed: z.boolean(),
  state: liveStateSchema,
})
export type LiveReceipt = z.infer<typeof liveReceiptSchema>
export const liveHistorySchema = z.object({
  ...envelope,
  operations: z.array(
    z.object({
      operationId: id,
      kind: z.string(),
      createdAt: z.string(),
      undone: z.boolean(),
      state: liveStateSchema,
    }),
  ),
})
export const liveVisitsSchema = z.object({
  ...envelope,
  visits: z.array(
    z.object({
      studentId: id,
      displayName: z.string(),
      lessonId: id,
      updatedAt: z.string(),
      changedCount: z.number().int(),
    }),
  ),
})
export const liveSessionReceiptSchema = z.object({ ...envelope, sessionId: id })
export const liveVisitReceiptSchema = liveVisitSchema.extend(envelope)
export const LIVE_REACTIONS = [
  { id: 300, label: 'Очень круто!', short: '👍 Круто' },
  { id: 301, label: 'Мутно', short: '🌫 Мутно' },
  { id: 304, label: 'Похоже на ИИ', short: '🤖 ИИ' },
  { id: 305, label: 'Помогают родители', short: '👪 Родители' },
  { id: 303, label: 'Проблемы со связью', short: '📡 Связь' },
] as const
