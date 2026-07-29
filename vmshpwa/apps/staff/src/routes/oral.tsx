import { createFileRoute } from '@tanstack/react-router'
import { useState, type FormEvent } from 'react'
import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'
import { PageLayout } from '@vmsh/app-shell'
import { Button, Input, Label } from '@vmsh/ui'

import { StaffOralWindowsPage } from '../staff-oral-windows-page'

const searchSchema = z.object({ groupLesson: publicIdSchema.optional() })
export const Route = createFileRoute('/oral')({
  validateSearch: searchSchema,
  component: OralRoute,
})

function OralRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const [groupLessonId, setGroupLessonId] = useState(search.groupLesson ?? '')
  if (search.groupLesson) {
    return <StaffOralWindowsPage groupLessonId={search.groupLesson} key={search.groupLesson} />
  }

  const open = (event: FormEvent) => {
    event.preventDefault()
    const parsed = publicIdSchema.safeParse(groupLessonId.trim())
    if (parsed.success) void navigate({ search: { groupLesson: parsed.data } })
  }
  return (
    <PageLayout
      description="Выберите групповое занятие, для которого нужно настроить окна устного приёма."
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
