import { BookOpen, CalendarClock, MapPin, Radio, Settings2 } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Switch, cn } from '@vmsh/ui'

import { LevelChip } from './level-chip'
import type { CourseEnrollmentView, CourseView, GroupView } from './types'

/*
 * Multi-course view components implement the hierarchy and switching contract
 * from docs/courses-groups-and-lessons.md and design-system Phase 4. They are
 * pure view-model compositions; applications own URL state and mutations.
 */

const accentClass: Record<CourseView['accentIndex'], string> = {
  0: 'border-border',
  1: 'border-l-chart-1',
  2: 'border-l-chart-2',
  3: 'border-l-chart-3',
  4: 'border-l-chart-4',
}

export interface CourseContextProps {
  courses: CourseView[]
  activeCourseId: string
  onCourseChange?: (courseId: string) => void
  label?: string
  className?: string
}

export function CourseContext({
  courses,
  activeCourseId,
  onCourseChange,
  label = 'Курс',
  className,
}: CourseContextProps) {
  return (
    <label className={cn('grid min-w-0 gap-1 text-label font-medium text-foreground', className)}>
      <span>{label}</span>
      <select
        className="min-h-(--touch-target) min-w-0 rounded-md border border-input bg-surface px-3 text-small"
        onChange={(event) => onCourseChange?.(event.target.value)}
        value={activeCourseId}
      >
        {courses.map((course) => (
          <option key={course.id} value={course.id}>
            {course.name}
          </option>
        ))}
      </select>
    </label>
  )
}

export interface CourseGroupSwitcherProps {
  course: CourseView
  groups: GroupView[]
  activeGroupId: string
  onChange?: (groupId: string) => void
  compact?: boolean
  helpText?: ReactNode
  className?: string
}

export function CourseGroupSwitcher({
  course,
  groups,
  activeGroupId,
  onChange,
  compact = false,
  helpText = 'Смена действует только внутри этого курса и требует подтверждения в приложении.',
  className,
}: CourseGroupSwitcherProps) {
  return (
    <fieldset className={cn('min-w-0 space-y-2', className)}>
      <legend className="text-label font-medium text-foreground">
        Группа курса «{course.name}»
      </legend>
      <div className="flex flex-wrap gap-1.5">
        {groups.map((group) => {
          const active = group.id === activeGroupId
          return (
            <button
              aria-pressed={active}
              className={cn(
                'rounded-md border px-2 py-1 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                active
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border bg-surface text-muted-foreground hover:bg-surface-subtle',
              )}
              key={group.id}
              onClick={() => onChange?.(group.id)}
              type="button"
            >
              <LevelChip compact={compact} level={group} />
            </button>
          )
        })}
      </div>
      {helpText ? <p className="text-caption text-muted-foreground">{helpText}</p> : null}
    </fieldset>
  )
}

export interface CourseCardProps {
  enrollment: CourseEnrollmentView
  lessonNumber: number
  lessonDate: string
  phase: string
  progressLabel: string
  nextAction?: ReactNode
  classroomName?: string
  onOpen?: () => void
  className?: string
}

export function CourseCard({
  enrollment,
  lessonNumber,
  lessonDate,
  phase,
  progressLabel,
  nextAction,
  classroomName,
  onOpen,
  className,
}: CourseCardProps) {
  const group =
    enrollment.allowedGroups.find((candidate) => candidate.id === enrollment.activeGroupId) ??
    enrollment.allowedGroups[0]

  return (
    <Card className={cn('border-l-4', accentClass[enrollment.course.accentIndex], className)}>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-caption text-muted-foreground">
              {enrollment.course.subjectCode} · занятие {lessonNumber} · {lessonDate}
            </p>
            <CardTitle>{enrollment.course.name}</CardTitle>
          </div>
          <Badge variant={enrollment.attendanceMode === 'in-person' ? 'info' : 'neutral'}>
            {enrollment.attendanceMode === 'in-person' ? (
              <MapPin aria-hidden="true" />
            ) : (
              <Radio aria-hidden="true" />
            )}
            {enrollment.attendanceMode === 'in-person' ? 'Очно' : 'Онлайн'}
          </Badge>
        </div>
        {group ? <LevelChip level={group} /> : null}
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="inline-flex items-center gap-1.5 text-small text-foreground">
              <CalendarClock aria-hidden="true" className="size-4 text-muted-foreground" />
              {phase}
            </p>
            <p className="inline-flex items-center gap-1.5 text-small text-muted-foreground">
              <BookOpen aria-hidden="true" className="size-4" />
              {progressLabel}
            </p>
          </div>
          {classroomName ? (
            <p className="text-small text-muted-foreground">Аудитория: {classroomName}</p>
          ) : null}
          {nextAction}
        </div>
        {onOpen ? (
          <Button onClick={onOpen} size="sm" variant="outline">
            Открыть курс
          </Button>
        ) : null}
      </CardContent>
    </Card>
  )
}

export interface CourseNotificationPreference {
  course: CourseView
  category: string
  label?: string
  enabled: boolean
  inherited: boolean
}

export function CourseNotificationSettings({
  preferences,
  onToggle,
  onReset,
  className,
}: {
  preferences: CourseNotificationPreference[]
  onToggle?: (courseId: string, category: string, enabled: boolean) => void
  onReset?: (courseId: string, category: string) => void
  className?: string
}) {
  return (
    <section className={cn('space-y-3', className)} aria-labelledby="course-notification-title">
      <div>
        <h2
          className="inline-flex items-center gap-2 text-section font-semibold text-foreground"
          id="course-notification-title"
        >
          <Settings2 aria-hidden="true" className="size-4" />
          Настройки по курсам
        </h2>
        <p className="text-caption text-muted-foreground">
          Значение курса переопределяет общую настройку только для выбранной категории.
        </p>
      </div>
      <ul className="divide-y divide-border rounded-md border border-border bg-surface">
        {preferences.map((preference) => (
          <li
            className="flex items-center justify-between gap-3 px-3 py-2"
            key={`${preference.course.id}:${preference.category}`}
          >
            <div>
              <p className="text-small font-medium text-foreground">{preference.course.name}</p>
              <p className="text-caption text-muted-foreground">
                {preference.label ?? preference.category} ·{' '}
                {preference.inherited ? 'общая настройка' : 'настройка курса'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!preference.inherited && onReset ? (
                <Button
                  onClick={() => onReset(preference.course.id, preference.category)}
                  size="sm"
                  variant="ghost"
                >
                  Общая
                </Button>
              ) : null}
              <Switch
                aria-label={`${preference.label ?? preference.category}, ${preference.course.name}`}
                checked={preference.enabled}
                onCheckedChange={(enabled) =>
                  onToggle?.(preference.course.id, preference.category, enabled)
                }
              />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
