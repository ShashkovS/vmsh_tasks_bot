import { CalendarDays, CopyCheck, MapPin, Users } from 'lucide-react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  cn,
} from '@vmsh/ui'

import { LevelChip } from './level-chip'
import type { CourseView, GroupView } from './types'

/* Calendar event composition replaces the former global lesson-scoped layout.
 * It follows docs/courses-groups-and-lessons.md and Phase 7 of the development
 * plan: selected group lessons may come from different courses and numbers.
 */

export interface InPersonGroupLessonView {
  id: string
  course: CourseView
  group: GroupView
  lessonNumber: number
  inPersonCount: number
  assignedCount: number
  inheritedRooms: string[]
  selected: boolean
}

function plural(count: number, one: string, few: string, many: string) {
  const mod100 = count % 100
  const mod10 = count % 10
  if (mod100 >= 11 && mod100 <= 14) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

export function InPersonEventComposer({
  title,
  startsAt,
  groupLessons,
  onToggle,
  onContinue,
  className,
}: {
  title: string
  startsAt: string
  groupLessons: InPersonGroupLessonView[]
  onToggle?: (groupLessonId: string, selected: boolean) => void
  onContinue?: () => void
  className?: string
}) {
  const selected = groupLessons.filter((groupLesson) => groupLesson.selected)
  const inheritedStudents = selected.reduce(
    (total, groupLesson) => total + groupLesson.assignedCount,
    0,
  )
  const inheritedRooms = new Set(selected.flatMap((groupLesson) => groupLesson.inheritedRooms))

  return (
    <section className={cn('max-w-5xl space-y-4', className)} aria-labelledby="event-title">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="inline-flex items-center gap-1.5 text-caption text-muted-foreground">
            <CalendarDays aria-hidden="true" className="size-4" />
            {startsAt}
          </p>
          <h2 className="text-page-title font-semibold text-foreground" id="event-title">
            {title}
          </h2>
          <p className="text-small text-muted-foreground">
            Выберите конкретные занятия групп. Номера в одном событии могут различаться.
          </p>
        </div>
        <Badge variant="info">
          {selected.length}{' '}
          {plural(selected.length, 'группа участвует', 'группы участвуют', 'групп участвуют')}
        </Badge>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {groupLessons.map((groupLesson) => (
          <Card key={groupLesson.id}>
            <CardHeader className="gap-2">
              <div className="flex items-start gap-2">
                <Checkbox
                  aria-label={`Включить ${groupLesson.course.name}, ${groupLesson.group.name}`}
                  checked={groupLesson.selected}
                  onCheckedChange={(checked) => onToggle?.(groupLesson.id, checked === true)}
                />
                <div className="min-w-0">
                  <p className="text-caption text-muted-foreground">
                    {groupLesson.course.name} · занятие {groupLesson.lessonNumber}
                  </p>
                  <CardTitle>
                    <LevelChip level={groupLesson.group} />
                  </CardTitle>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-2 text-small text-muted-foreground sm:grid-cols-3">
              <p className="inline-flex items-center gap-1.5">
                <Users aria-hidden="true" className="size-4" />
                {groupLesson.inPersonCount} очно
              </p>
              <p>{groupLesson.assignedCount} уже назначены</p>
              <p className="inline-flex items-center gap-1.5">
                <MapPin aria-hidden="true" className="size-4" />
                {groupLesson.inheritedRooms.join(', ') || 'нет комнат'}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Alert tone="info">
        <CopyCheck aria-hidden="true" />
        <AlertContent>
          <AlertTitle>
            Будет перенесено {inheritedRooms.size}{' '}
            {plural(inheritedRooms.size, 'аудитория', 'аудитории', 'аудиторий')} и{' '}
            {inheritedStudents}{' '}
            {plural(inheritedStudents, 'назначение', 'назначения', 'назначений')}
          </AlertTitle>
          <AlertDescription>
            Новый черновик полностью повторит последний подтверждённый план выбранных групп.
            Администратор скорректирует только изменения состава, режима или комнат.
          </AlertDescription>
        </AlertContent>
      </Alert>

      <div className="flex flex-wrap gap-2">
        <Button disabled={selected.length === 0} onClick={onContinue}>
          Подготовить план аудиторий
        </Button>
        <p className="self-center text-caption text-muted-foreground">
          Пересечение курсов показывает предупреждение, но не создаёт отдельный процесс.
        </p>
      </div>
    </section>
  )
}
