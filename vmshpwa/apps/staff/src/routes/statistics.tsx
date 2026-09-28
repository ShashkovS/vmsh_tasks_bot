import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { t } from '@lingui/core/macro'
import { Button } from '@vmsh/ui'
import { StaffStatisticsReports } from '../staff-statistics-reports'

import { publicIdSchema } from '@vmsh/contracts'

import { StaffStatisticsPage } from '../staff-statistics-page'

const searchSchema = z.object({
  view: z.enum(['summary', 'plus-table', 'analytics']).optional().catch(undefined),
  course: publicIdSchema.optional().catch(undefined),
  group: publicIdSchema.optional().catch(undefined),
  lesson: z.coerce.number().int().nonnegative().optional().catch(undefined),
  student: publicIdSchema.optional().catch(undefined),
})

export const Route = createFileRoute('/statistics')({
  validateSearch: searchSchema,
  component: StatisticsRoute,
})

function StatisticsRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const view = search.view ?? 'summary'
  const onCourseChange = (course: string) =>
    void navigate({ search: { view, course }, replace: true })
  const onGroupChange = (group: string | null, lesson?: number | null) =>
    void navigate({
      search: {
        ...search,
        group: group ?? undefined,
        lesson: lesson ?? search.lesson,
        student: undefined,
      },
    })
  const onLessonChange = (lesson: number) => void navigate({ search: { ...search, lesson } })
  const filters = {
    courseId: search.course ?? null,
    groupId: search.group ?? null,
    lessonNumber: search.lesson ?? null,
    onCourseChange,
    onGroupChange,
    onLessonChange,
  }
  return (
    <>
      <nav className="flex flex-wrap gap-2 px-4 pt-4" aria-label={t`Разделы статистики`}>
        {(
          [
            ['summary', t`Сводка курса`],
            ['plus-table', t`Таблица плюсов`],
            ['analytics', t`Сложность и распределения`],
          ] as const
        ).map(([value, label]) => (
          <Button
            key={value}
            variant={view === value ? 'secondary' : 'ghost'}
            aria-current={view === value ? 'page' : undefined}
            onClick={() => void navigate({ search: { ...search, view: value } })}
          >
            {label}
          </Button>
        ))}
      </nav>
      {view === 'analytics' ? (
        <StaffStatisticsPage
          {...filters}
          studentId={search.student ?? null}
          onStudentChange={(student) =>
            void navigate({ search: { ...search, student: student ?? undefined } })
          }
        />
      ) : (
        <StaffStatisticsReports {...filters} kind={view} />
      )}
    </>
  )
}
