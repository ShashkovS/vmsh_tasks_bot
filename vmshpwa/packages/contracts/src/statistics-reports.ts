import { z } from 'zod'
import { publicIdSchema } from './auth'
import { statisticsCourseSchema } from './staff-statistics'

// docs/lesson-statistics.md: current credit is separate from review workload.
const count = z.number().int().nonnegative()
const credit = z.number().nonnegative()
const envelope = z.object({
  schemaVersion: z.literal(1),
  courses: z.array(statisticsCourseSchema),
  selectedCourseId: publicIdSchema.nullable(),
  selectedGroupId: publicIdSchema.nullable(),
  requestId: z.string(),
})
export const statisticsSummarySchema = envelope.extend({
  lessons: z.array(
    z
      .object({
        lessonNumber: count,
        students: count,
        allPlus: credit,
        botPlus: credit,
        writtenPlus: credit,
        writtenWrittenPlus: credit,
        writtenOralPlus: credit,
        zoomPlus: credit,
        schoolPlus: credit,
        writtenChecked: count,
        writtenPending: count,
        writtenTotal: count,
        writtenStudents: count,
        zoomStudents: count,
        schoolStudents: count,
      })
      .superRefine((row, ctx) => {
        if (row.writtenTotal !== row.writtenChecked + row.writtenPending)
          ctx.addIssue({ code: 'custom', message: 'Written workload must balance' })
        if (row.allPlus !== row.botPlus + row.writtenPlus + row.zoomPlus + row.schoolPlus)
          ctx.addIssue({ code: 'custom', message: 'Credit channels must balance' })
      }),
  ),
})
export const statisticsPlusTableSchema = envelope
  .extend({
    lessonNumbers: z.array(count),
    lessonNumber: count.nullable(),
    problems: z.array(
      z.object({ problemId: publicIdSchema, label: z.string(), title: z.string() }),
    ),
    rows: z.array(
      z.object({
        studentId: publicIdSchema,
        name: z.string(),
        total: credit,
        cells: z.array(
          z.object({
            score: z.union([z.literal(0), z.literal(0.5), z.literal(1)]),
            source: z.enum(['bot', 'written', 'zoom', 'school']).nullable(),
            attempted: z.boolean(),
            pending: z.boolean(),
          }),
        ),
      }),
    ),
  })
  .superRefine((table, ctx) => {
    for (const row of table.rows) {
      if (
        row.cells.length !== table.problems.length ||
        row.total !== row.cells.reduce((n, c) => n + c.score, 0)
      )
        ctx.addIssue({ code: 'custom', message: 'Matrix columns and totals must match' })
    }
  })
export type StatisticsSummary = z.infer<typeof statisticsSummarySchema>
export type StatisticsPlusTable = z.infer<typeof statisticsPlusTableSchema>
