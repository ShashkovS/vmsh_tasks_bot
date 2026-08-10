import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'

import { StaffStatisticsPage } from '../staff-statistics-page'

const searchSchema = z.object({
  course: publicIdSchema.optional().catch(undefined),
  group: publicIdSchema.optional().catch(undefined),
  lesson: z.coerce.number().int().nonnegative().optional().catch(undefined),
})

export const Route = createFileRoute('/statistics')({
  validateSearch: searchSchema,
  component: StatisticsRoute,
})

function StatisticsRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StaffStatisticsPage
      courseId={search.course ?? null}
      groupId={search.group ?? null}
      lessonNumber={search.lesson ?? null}
      onCourseChange={(course) =>
        void navigate({ search: { course, group: undefined, lesson: undefined }, replace: true })
      }
      onGroupChange={(group) =>
        void navigate({ search: { ...search, group: group ?? undefined, lesson: undefined } })
      }
      onLessonChange={(lesson) => void navigate({ search: { ...search, lesson } })}
    />
  )
}
