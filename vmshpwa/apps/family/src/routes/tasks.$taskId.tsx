import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { contentMaterialKindSchema, publicIdSchema } from '@vmsh/contracts'

import { FamilyPublishedContentPage } from '../content-page'

const familyTaskContentSearchSchema = z.object({
  groupLesson: publicIdSchema.optional(),
  // Keep the implicit condition default out of the address bar; this also
  // preserves an anonymous deep link exactly across the login redirect.
  material: contentMaterialKindSchema.optional().catch(undefined),
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
      kind={search.material ?? 'condition'}
      taskId={Route.useParams().taskId}
      {...(search.groupLesson ? { groupLessonId: search.groupLesson } : {})}
      {...(search.problem ? { problemOrdinal: search.problem } : {})}
      {...(search.student ? { requestedStudentPublicId: search.student } : {})}
    />
  )
}
