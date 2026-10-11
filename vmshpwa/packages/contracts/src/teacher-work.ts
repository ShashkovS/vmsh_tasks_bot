import { z } from 'zod'
import { publicIdSchema } from './auth'

// docs/teacher-work.md: nullable hours mean incomplete evidence, never absence.
const count = z.number().int().nonnegative()
const hours = z.number().finite().nonnegative().nullable()
const kind = z.enum(['school', 'zoom', 'written'])
const source = z.enum(['log', 'series', 'estimate', 'roster', 'manual', 'unknown'])
const operation = z
  .object({
    id: count,
    state: z.enum(['queued', 'running', 'completed', 'failed']),
    startedAt: z.string(),
    completedAt: z.string().nullable(),
    errorCode: z.string().nullable(),
  })
  .nullable()
export const teacherWorkStatusSchema = z.object({ operation, busy: z.boolean() })
export const teacherWorkCatalogSchema = z.object({
  courses: z.array(
    z.object({
      courseId: publicIdSchema,
      name: z.string(),
      status: z.enum(['active', 'draft', 'archived']),
    }),
  ),
  teachers: z.array(
    z.object({
      teacherId: publicIdSchema,
      id: count,
      surname: z.string(),
      name: z.string(),
      middlename: z.string().nullable(),
    }),
  ),
})
export const teacherWorkReportSchema = z
  .object({
    run: operation,
    operation,
    lessons: z.array(z.object({ number: count, anchor: z.string() })),
    columns: z.array(
      z.object({ key: z.string(), lesson: count, kind, date: z.string(), label: z.string() }),
    ),
    rows: z.array(
      z.object({
        teacherId: publicIdSchema,
        id: count,
        surname: z.string(),
        name: z.string(),
        middlename: z.string(),
        counts: z.object({ school: count, zoom: count, written: count }),
        totals: z.object({ school: hours, zoom: hours, written: hours }),
        totalHours: hours,
        cells: z.array(
          z.object({
            columnKey: z.string(),
            keys: z.array(z.string()),
            hours,
            sources: z.array(source),
            stale: z.boolean(),
            anomalies: z.array(z.string()),
          }),
        ),
      }),
    ),
    tsv: z.string(),
  })
  .superRefine((report, ctx) => {
    if (report.rows.some((row) => row.cells.length !== report.columns.length))
      ctx.addIssue({ code: 'custom', message: 'Teacher-work matrix must be rectangular' })
  })
const candidate = z.object({ teacherId: publicIdSchema, label: z.string(), score: z.number() })
const rosterRow = z.object({
  rowId: z.string(),
  name: z.string(),
  room: z.string(),
  startsTime: z.string().nullable(),
  endsTime: z.string().nullable(),
  teacherId: publicIdSchema.nullable(),
  source: z.string(),
  candidates: z.array(candidate),
})
export const teacherWorkStoredRowsSchema = z.array(rosterRow.omit({ candidates: true }))
export const teacherWorkRosterBaseSchema = z.object({
  eventId: publicIdSchema,
  eventVersion: count,
  expectedVersion: count,
})
export const teacherWorkPreviewSchema = z.object({
  rows: z.array(rosterRow),
  notes: z.array(z.string()),
  eventCandidates: z.array(publicIdSchema),
  preliminary: z.boolean(),
  sourceSha256: z.string(),
})
const event = z.object({
  id: count,
  public_id: publicIdSchema,
  name: z.string(),
  starts_at: z.string(),
  ends_at: z.string(),
  version: count,
})
const alias = z
  .object({
    teacher_id: count.nullable(),
    state: z.enum(['mapped', 'ignored', 'unresolved']),
    version: count,
  })
  .nullable()
export const teacherWorkInputsSchema = z.object({
  timezone: z.string(),
  shifts: z.array(
    z.object({
      teacherId: publicIdSchema,
      eventId: publicIdSchema,
      normHours: z.number(),
      standardStartsAt: z.string(),
      standardEndsAt: z.string(),
    }),
  ),
  settings: z.object({ norm_hours: z.number(), version: count }),
  events: z.array(event),
  signatures: z.array(
    z.object({
      name: z.string(),
      count,
      firstAt: z.string(),
      lastAt: z.string(),
      teacherLike: z.boolean(),
      alias,
      examples: z.array(
        z.object({
          id: count,
          event: z.string(),
          event_ts: z.string(),
          zoom_user_id: z.union([z.number(), z.string()]).nullable(),
        }),
      ),
      candidates: z.array(candidate),
    }),
  ),
  rosters: z.array(
    z.object({
      eventPublicId: publicIdSchema,
      state: z.enum(['draft', 'confirmed']),
      version: count,
      raw_text: z.string(),
      rows_json: z.string(),
      updated_at: z.string(),
    }),
  ),
})
export const teacherWorkDetailsSchema = z.object({
  cell: z.object({
    key: z.string(),
    kind,
    teacherId: publicIdSchema,
    slot: z.string(),
    hours,
    source,
    fingerprint: z.string(),
    evidence: z.unknown(),
    anomalies: z.array(z.string()),
  }),
  override: z
    .object({
      hours: hours,
      comment: z.string(),
      source_fingerprint: z.string(),
      version: count,
      updated_at: z.string(),
      updated_by: count,
    })
    .nullable(),
  audit: z.array(
    z.object({
      action: z.string(),
      created_at: z.string(),
      surname: z.string(),
      name: z.string(),
      before_json: z.string().nullable(),
      after_json: z.string(),
    }),
  ),
})
const base = z.object({
  courseId: publicIdSchema,
  idempotencyKey: z.string().min(1).max(128),
  expectedVersion: count,
})
export const teacherWorkCommandSchema = z.discriminatedUnion('action', [
  base.extend({ action: z.literal('settings'), normHours: z.number().min(0).max(24) }),
  base.extend({
    action: z.literal('alias'),
    name: z.string().min(1).max(500),
    state: z.enum(['mapped', 'ignored', 'unresolved']),
    teacherId: publicIdSchema.nullable(),
  }),
  base.extend({
    action: z.literal('override'),
    cellKey: z.string(),
    hours,
    comment: z.string().trim().min(1).max(2000),
    sourceFingerprint: z.string(),
  }),
  base.extend({
    action: z.literal('roster'),
    eventId: publicIdSchema,
    eventVersion: count,
    rawText: z.string().min(1).max(100000),
    state: z.enum(['draft', 'confirmed']),
    replace: z.boolean(),
    rows: z.array(rosterRow.omit({ candidates: true })),
  }),
])
export const teacherWorkReceiptSchema = z.object({ version: count })
export type TeacherWorkReport = z.infer<typeof teacherWorkReportSchema>
export type TeacherWorkCatalog = z.infer<typeof teacherWorkCatalogSchema>
export type TeacherWorkInputs = z.infer<typeof teacherWorkInputsSchema>
export type TeacherWorkPreview = z.infer<typeof teacherWorkPreviewSchema>
export type TeacherWorkDetails = z.infer<typeof teacherWorkDetailsSchema>
export type TeacherWorkCommand = z.infer<typeof teacherWorkCommandSchema>
