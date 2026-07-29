import { createFileRoute } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'
import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'
import { PageLayout, useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { Button, Input, Label } from '@vmsh/ui'

import { StaffOralResultsPage } from '../staff-oral-results-page'
import { StaffOralWindowsPage } from '../staff-oral-windows-page'

const searchSchema = z.object({
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
  const [groupLessonId, setGroupLessonId] = useState(search.groupLesson ?? '')
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

  const open = (event: FormEvent) => {
    event.preventDefault()
    const parsed = publicIdSchema.safeParse(groupLessonId.trim())
    if (parsed.success) void navigate({ search: { groupLesson: parsed.data, tab: 'results' } })
  }
  return (
    <PageLayout
      description="Выберите групповое занятие для внесения результатов или настройки окон устного приёма."
      title="Устный приём"
      width="reading"
    >
      <form className="flex items-end gap-2" onSubmit={open}>
        <div className="min-w-0 flex-1 space-y-1">
          <Label htmlFor="oral-group-lesson">ID группового занятия</Label>
          <Input
            id="oral-group-lesson"
            onChange={(event) => setGroupLessonId(event.target.value)}
            placeholder="group-lesson-41-n"
            value={groupLessonId}
          />
        </div>
        <Button type="submit">Открыть</Button>
      </form>
    </PageLayout>
  )
}
