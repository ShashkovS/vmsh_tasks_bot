import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { FamilyReadableContentPage } from '../content-page'

const searchSchema = z.object({
  child: z.coerce.number().int().positive().optional().catch(undefined),
})

export const Route = createFileRoute('/tasks/$courseCode/$groupCode/$lessonNumber')({
  validateSearch: searchSchema,
  component: FamilyReadableTaskRoute,
})

function FamilyReadableTaskRoute() {
  const params = Route.useParams()
  const search = Route.useSearch()
  return (
    <FamilyReadableContentPage
      {...(search.child ? { childNumber: search.child } : {})}
      courseCode={params.courseCode}
      groupCode={params.groupCode}
      lessonNumber={Number(params.lessonNumber)}
    />
  )
}
