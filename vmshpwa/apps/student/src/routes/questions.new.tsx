import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'

import { StudentNewSupportPage } from '../student-support-pages'

const newQuestionSearchSchema = z.object({
  groupLesson: publicIdSchema,
  problem: publicIdSchema.optional(),
})

export const Route = createFileRoute('/questions/new')({
  validateSearch: newQuestionSearchSchema,
  component: NewStudentQuestionRoute,
})

function NewStudentQuestionRoute() {
  const search = Route.useSearch()
  return (
    <StudentNewSupportPage
      key={`${search.groupLesson}:${search.problem ?? 'general'}`}
      groupLessonId={search.groupLesson}
      {...(search.problem ? { problemId: search.problem } : {})}
    />
  )
}
