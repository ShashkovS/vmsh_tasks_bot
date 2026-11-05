import { z } from 'zod'
import { publicIdSchema, type LiveCell, type LiveCells, type LiveCatalog } from '@vmsh/contracts'

export const liveSearchSchema = z.object({
  course: publicIdSchema.optional(),
  event: publicIdSchema.optional(),
  room: publicIdSchema.optional(),
  student: publicIdSchema.optional(),
  lesson: publicIdSchema.optional(),
  session: publicIdSchema.optional(),
  oralOnly: z.boolean().optional(),
  presentOnly: z.boolean().optional(),
})
export type LiveSearch = z.infer<typeof liveSearchSchema>

export const liveCellKey = (studentId: string, problemId: string) => `${studentId}:${problemId}`
export const emptyLiveCell = (studentId: string, problemId: string): LiveCell => ({
  studentId,
  problemId,
  version: 0,
  verdict: null,
  symbol: '',
  teacherId: null,
  updatedAt: null,
})

// live-marking.md: responses may cross receipts in flight. Tombstones retain
// their versions; a changed membership scope discards no-longer-visible pupils.
export function mergeLiveCells(current: LiveCells, latest?: LiveCells): LiveCells {
  if (!latest || current.scope !== latest.scope) return current
  const updates = new Map(
    current.cells.map((cell) => [liveCellKey(cell.studentId, cell.problemId), cell]),
  )
  for (const cell of latest.cells) {
    const id = liveCellKey(cell.studentId, cell.problemId)
    const update = updates.get(id)
    if (!update || update.version < cell.version) updates.set(id, cell)
  }
  return { ...current, cells: [...updates.values()] }
}

// docs/live-marking.md: an explicit worksheet is independent of enrollment in Zoom.
type Lesson = LiveCatalog['courses'][number]['lessons'][number]
export function zoomLessonSelection(catalog: Lesson[], studentGroup?: string, lessonId?: string) {
  const lesson =
    catalog.find((item) => item.lessonId === lessonId) ??
    catalog.find((item) => item.groupId === studentGroup)
  const groupId = lesson?.groupId ?? studentGroup
  const groups = [...new Map(catalog.map((item) => [item.groupId, item.groupName])).entries()].map(
    ([id, name]) => ({
      id,
      name,
      target: catalog.find(
        (item) => item.groupId === id && (!lesson || item.number === lesson.number),
      ),
    }),
  )
  return { lesson, groupId, groups, lessons: catalog.filter((item) => item.groupId === groupId) }
}
