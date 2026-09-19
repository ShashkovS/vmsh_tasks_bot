import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'
import { LiveMarkingPage } from '../live-marking-page'
import { liveSearchSchema } from '../live-marking-state'
import { useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { Button } from '@vmsh/ui'

import { StaffOralResultsPage } from '../staff-oral-results-page'
import { StaffOralWindowsPage } from '../staff-oral-windows-page'

const searchSchema = liveSearchSchema.extend({
  groupLesson: publicIdSchema.optional(),
  tab: z.enum(['results', 'windows']).optional(),
})
export const Route = createFileRoute('/oral')({
  validateSearch: searchSchema,
  component: OralRoute,
})

function OralRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const principal = useAuthenticatedPrincipal()
  if (search.groupLesson) {
    const tab = search.tab ?? 'results'
    return (
      <div>
        <nav aria-label="Разделы устного приёма" className="mx-auto flex max-w-7xl gap-1 px-4 pt-4">
          <Button
            onClick={() =>
              void navigate({ search: { groupLesson: search.groupLesson, tab: 'results' } })
            }
            size="sm"
            variant={tab === 'results' ? 'secondary' : 'ghost'}
          >
            Результаты
          </Button>
          {principal.audience === 'staff' && principal.role === 'admin' ? (
            <Button
              onClick={() =>
                void navigate({ search: { groupLesson: search.groupLesson, tab: 'windows' } })
              }
              size="sm"
              variant={tab === 'windows' ? 'secondary' : 'ghost'}
            >
              Окна приёма
            </Button>
          ) : null}
        </nav>
        {tab === 'windows' ? (
          <StaffOralWindowsPage groupLessonId={search.groupLesson} key={search.groupLesson} />
        ) : (
          <StaffOralResultsPage groupLessonId={search.groupLesson} key={search.groupLesson} />
        )}
      </div>
    )
  }

  return (
    <LiveMarkingPage
      mode="zoom"
      search={search}
      onSearch={(next) => {
        void navigate({ search: next })
      }}
    />
  )
}
