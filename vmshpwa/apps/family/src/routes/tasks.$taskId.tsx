import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { contentMaterialKindSchema, publicIdSchema } from '@vmsh/contracts'

import { FamilyPublishedContentPage } from '../content-page'

const familyTaskContentSearchSchema = z.object({
  groupLesson: publicIdSchema.optional(),
  material: contentMaterialKindSchema.catch('condition'),
  problem: z.coerce.number().int().positive().optional(),
  student: publicIdSchema.optional(),
})

export const Route = createFileRoute('/tasks/$taskId')({
  validateSearch: familyTaskContentSearchSchema,
  component: FamilyTaskRoute,
})

function FamilyTaskRoute() {
  const search = Route.useSearch()
  return (
    <FamilyPublishedContentPage
      kind={search.material}
      taskId={Route.useParams().taskId}
      {...(search.groupLesson ? { groupLessonId: search.groupLesson } : {})}
      {...(search.problem ? { problemOrdinal: search.problem } : {})}
      {...(search.student ? { requestedStudentPublicId: search.student } : {})}
    />
  )
}
