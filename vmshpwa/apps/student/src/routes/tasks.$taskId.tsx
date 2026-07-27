import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { contentMaterialKindSchema, publicIdSchema } from '@vmsh/contracts'

import { StudentPublishedContentPage } from '../content-page'

const taskContentSearchSchema = z.object({
  groupLesson: publicIdSchema.optional(),
  // Keep an omitted default out of the URL so auth redirects preserve a
  // shared deep link byte-for-byte. The component applies the product default.
  material: contentMaterialKindSchema.optional().catch(undefined),
  problem: z.coerce.number().int().positive().optional(),
})

export const Route = createFileRoute('/tasks/$taskId')({
  validateSearch: taskContentSearchSchema,
  component: StudentTaskRoute,
})

function StudentTaskRoute() {
  const search = Route.useSearch()
  return (
    <StudentPublishedContentPage
      kind={search.material ?? 'condition'}
      taskId={Route.useParams().taskId}
      {...(search.groupLesson ? { groupLessonId: search.groupLesson } : {})}
      {...(search.problem ? { problemOrdinal: search.problem } : {})}
    />
  )
}
