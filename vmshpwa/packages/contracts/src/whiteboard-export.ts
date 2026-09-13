import { z } from 'zod'
import { publicIdSchema } from './auth'
import { webContentDocumentSchema } from './content'

export const whiteboardSheetSchema = z.object({
  groupLessonId: publicIdSchema,
  courseId: publicIdSchema,
  courseCode: z.string(),
  courseName: z.string(),
  lessonNumber: z.number().int().positive(),
  lessonTitle: z.string().nullable(),
  groupId: publicIdSchema,
  groupCode: z.string(),
  groupName: z.string(),
  publicationId: publicIdSchema,
  revisionId: publicIdSchema,
})
export const whiteboardCatalogSchema = z.object({ sheets: z.array(whiteboardSheetSchema) })
export const whiteboardExportSchema = z.object({
  sheet: whiteboardSheetSchema,
  document: webContentDocumentSchema,
  statistics: z
    .object({
      participantCount: z.number().int().nonnegative(),
      generatedAt: z.string(),
      problems: z.array(
        z.object({
          problemId: publicIdSchema,
          label: z.string(),
          title: z.string().nullable(),
          points: z.number().nonnegative(),
          tried: z.number().int().nonnegative(),
          share: z.number().nullable(),
        }),
      ),
    })
    .nullable(),
  statisticsError: z.boolean(),
})
export type WhiteboardExport = z.infer<typeof whiteboardExportSchema>
export type WhiteboardSheet = z.infer<typeof whiteboardSheetSchema>
