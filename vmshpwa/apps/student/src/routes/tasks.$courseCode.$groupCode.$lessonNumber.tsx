import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StudentReadableTaskPage } from '../student-readable-task-page'

const searchSchema = z.object({
  task: z.string().trim().min(1).max(80).optional().catch(undefined),
})

export const Route = createFileRoute('/tasks/$courseCode/$groupCode/$lessonNumber')({
  validateSearch: searchSchema,
  component: ReadableTaskRoute,
})

function ReadableTaskRoute() {
  const params = Route.useParams()
  const search = Route.useSearch()
  return (
    <StudentReadableTaskPage
      courseCode={params.courseCode}
      {...(search.task ? { displayNumber: search.task } : {})}
      groupCode={params.groupCode}
      lessonNumber={Number(params.lessonNumber)}
    />
  )
}
