import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'

import { ProblemSynonymPage } from '../problem-synonym-page'

const searchSchema = z.object({
  lesson: publicIdSchema.optional().catch(undefined),
})

export const Route = createFileRoute('/problems/synonyms')({
  validateSearch: searchSchema,
  component: ProblemSynonymRoute,
})

function ProblemSynonymRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <ProblemSynonymPage
      {...(search.lesson ? { courseLessonId: search.lesson } : {})}
      onCourseLessonChange={(lesson) => void navigate({ search: { lesson } })}
    />
  )
}
