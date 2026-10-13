import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import {
  Archive,
  BookOpenCheck,
  MessageSquareText,
  Plus,
  RadioTower,
  Settings2,
} from 'lucide-react'

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  cn,
} from '@vmsh/ui'

import { LevelChip } from './level-chip'
import type { CourseView, GroupView } from './types'

/* Staff administration prototypes for the season → course → group model from
 * docs/courses-groups-and-lessons.md. These components intentionally contain
 * no API calls; backend CRUD is implemented in development plan Phase 10.
 */

export interface ManagedGroup extends GroupView {
  status: 'draft' | 'active' | 'archived'
  activeStudents: number
  scheduleLabel: string
}

export interface ManagedCourse {
  course: CourseView
  status: 'draft' | 'active' | 'archived'
  groups: ManagedGroup[]
}

export function CourseGroupCatalog({
  courses,
  onAddCourse,
  onAddGroup,
  onEditCourse,
  onEditGroup,
  onArchiveCourse,
  className,
}: {
  courses: ManagedCourse[]
  onAddCourse?: () => void
  onAddGroup?: (courseId: string) => void
  onEditCourse?: (courseId: string) => void
  onEditGroup?: (groupId: string) => void
  onArchiveCourse?: (courseId: string) => void
  className?: string
}) {
  return (
    <section className={cn('space-y-4', className)} aria-labelledby="course-catalog-title">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-page-title font-semibold text-foreground" id="course-catalog-title">
            <Trans>Курсы и группы</Trans>
          </h2>
          <p className="text-small text-muted-foreground">
            <Trans>Сезон 2025–2026 · названия групп уникальны только внутри курса.</Trans>
          </p>
        </div>
        <Button onClick={onAddCourse} size="sm">
          <Plus aria-hidden="true" />
          <Trans>Добавить курс</Trans>
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        {courses.map(({ course, groups, status }) => (
          <Card className="min-w-0" key={course.id}>
            <CardHeader className="gap-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-mono text-caption text-muted-foreground">{course.code}</p>
                  <CardTitle>{course.name}</CardTitle>
                  <p className="text-caption text-muted-foreground">{course.subjectCode}</p>
                </div>
                <Badge
                  variant={
                    status === 'active' ? 'success' : status === 'draft' ? 'warning' : 'neutral'
                  }
                >
                  {status === 'active'
                    ? t`Активен`
                    : status === 'draft'
                      ? t`Черновик`
                      : t`В архиве`}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button onClick={() => onEditCourse?.(course.id)} size="xs" variant="outline">
                  <Settings2 aria-hidden="true" />
                  <Trans>Настроить</Trans>
                </Button>
                <Button onClick={() => onAddGroup?.(course.id)} size="xs" variant="ghost">
                  <Plus aria-hidden="true" />
                  <Trans>Группа</Trans>
                </Button>
                <Button onClick={() => onArchiveCourse?.(course.id)} size="xs" variant="ghost">
                  <Archive aria-hidden="true" />
                  {status === 'archived' ? t`Восстановить` : t`В архив`}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="divide-y divide-border rounded-md border border-border">
                {groups.map((group) => (
                  <li
                    className="grid gap-1 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                    key={group.id}
                  >
                    <div className="min-w-0">
                      <LevelChip level={group} />
                      <p className="mt-1 text-caption text-muted-foreground">
                        <Trans>
                          {group.activeStudents} учеников · {group.scheduleLabel}
                        </Trans>
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge variant={group.status === 'active' ? 'neutral' : 'warning'}>
                        {group.status === 'active'
                          ? t`Активна`
                          : group.status === 'draft'
                            ? t`Черновик`
                            : t`Скрыта`}
                      </Badge>
                      {onEditGroup ? (
                        <Button
                          aria-label={t`Изменить группу ${group.name}`}
                          onClick={() => onEditGroup(group.id)}
                          size="icon-xs"
                          variant="ghost"
                        >
                          <Settings2 aria-hidden="true" />
                        </Button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}

export type ScheduleSource = 'course' | 'group' | 'lesson' | 'disabled'

export interface IndependentScheduleRow {
  group: GroupView
  source: ScheduleSource
  conditionAt: string
  hintAt: string
  closesAt: string
  solutionAt: string
  snapshotLabel: string
}

const sourceLabel: Record<ScheduleSource, string> = {
  get course() {
    return t`Шаблон курса`
  },
  get group() {
    return t`Переопределено группой`
  },
  get lesson() {
    return t`Изменено для занятия`
  },
  get disabled() {
    return t`Отключено`
  },
}

export function IndependentScheduleMatrix({
  course,
  lessonNumber,
  rows,
  onEdit,
  className,
}: {
  course: CourseView
  lessonNumber: number
  rows: IndependentScheduleRow[]
  onEdit?: (groupId: string) => void
  className?: string
}) {
  return (
    <section className={cn('space-y-3', className)} aria-labelledby="schedule-matrix-title">
      <div>
        <h2 className="text-section font-semibold text-foreground" id="schedule-matrix-title">
          <Trans>
            {course.name} · занятие {lessonNumber}
          </Trans>
        </h2>
        <p className="text-small text-muted-foreground">
          <Trans>
            Даты материализованы для каждой группы. Изменение шаблона не сдвигает этот снимок.
          </Trans>
        </p>
      </div>
      <div className="overflow-x-auto rounded-md border border-border" data-density="staff">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Trans>Группа</Trans>
              </TableHead>
              <TableHead>
                <Trans>Источник</Trans>
              </TableHead>
              <TableHead>
                <Trans>Условие</Trans>
              </TableHead>
              <TableHead>
                <Trans>Подсказка</Trans>
              </TableHead>
              <TableHead>
                <Trans>Приём до</Trans>
              </TableHead>
              <TableHead>
                <Trans>Решение</Trans>
              </TableHead>
              <TableHead>
                <Trans>Действие</Trans>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.group.id}>
                <TableCell>
                  <LevelChip level={row.group} />
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      row.source === 'course'
                        ? 'neutral'
                        : row.source === 'disabled'
                          ? 'warning'
                          : 'info'
                    }
                  >
                    {sourceLabel[row.source]}
                  </Badge>
                  <p className="mt-1 text-caption text-muted-foreground">{row.snapshotLabel}</p>
                </TableCell>
                {[row.conditionAt, row.hintAt, row.closesAt, row.solutionAt].map((value, index) => (
                  <TableCell className="whitespace-nowrap font-num text-caption" key={index}>
                    {value || '—'}
                  </TableCell>
                ))}
                <TableCell>
                  <Button onClick={() => onEdit?.(row.group.id)} size="xs" variant="outline">
                    <Trans>Изменить</Trans>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  )
}

export interface TelegramBindingView {
  id: string
  owner: 'course' | 'group'
  ownerLabel: string
  purpose: 'news-source' | 'materials-target'
  chatLabel: string
  topicLabel?: string
  inherited?: boolean
  status: 'draft' | 'verified' | 'disabled'
}

export function TelegramBindingsEditor({
  course,
  bindings,
  onAdd,
  onDisable,
  onRestore,
  onVerify,
  pendingBindingId,
  className,
}: {
  course: CourseView
  bindings: TelegramBindingView[]
  onAdd?: () => void
  onDisable?: (bindingId: string) => void
  onRestore?: (bindingId: string) => void
  onVerify?: (bindingId: string) => void
  pendingBindingId?: string | null
  className?: string
}) {
  return (
    <section className={cn('space-y-3', className)} aria-labelledby="telegram-bindings-title">
      <div className="flex flex-col items-stretch gap-2 md:flex-row md:flex-wrap md:items-end md:justify-between">
        <div className="min-w-0 md:flex-1">
          <h2
            className="inline-flex items-center gap-2 text-section font-semibold text-foreground"
            id="telegram-bindings-title"
          >
            <RadioTower aria-hidden="true" className="size-4" />
            Telegram · {course.name}
          </h2>
          <p className="text-small text-muted-foreground">
            <Trans>
              Новости курса складываются с групповыми. Цели материалов группы заменяют настройки
              курса по умолчанию.
            </Trans>
          </p>
        </div>
        <Button className="self-start" onClick={onAdd} size="sm" variant="outline">
          <Plus aria-hidden="true" />
          <Trans>Добавить привязку</Trans>
        </Button>
      </div>
      <ul className="divide-y divide-border rounded-md border border-border bg-surface">
        {bindings.map((binding) => {
          const PurposeIcon = binding.purpose === 'news-source' ? MessageSquareText : BookOpenCheck
          return (
            <li
              className="grid gap-2 px-3 py-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-center"
              key={binding.id}
            >
              <div>
                <p className="text-small font-medium text-foreground">{binding.ownerLabel}</p>
                <p className="text-caption text-muted-foreground">
                  {binding.owner === 'course' ? t`Курс` : t`Группа`}
                  {binding.inherited ? t` · наследуется` : ''}
                </p>
              </div>
              <div>
                <p className="inline-flex items-center gap-1.5 text-small text-foreground">
                  <PurposeIcon aria-hidden="true" className="size-4 text-muted-foreground" />
                  {binding.purpose === 'news-source'
                    ? t`Источник новостей`
                    : t`Публикация материалов`}
                </p>
                <p className="font-mono text-caption text-muted-foreground">
                  {binding.chatLabel}
                  {binding.topicLabel ? ` · ${binding.topicLabel}` : ''}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-1.5">
                <Badge
                  variant={
                    binding.status === 'verified'
                      ? 'success'
                      : binding.status === 'draft'
                        ? 'warning'
                        : 'neutral'
                  }
                >
                  {binding.status === 'verified'
                    ? t`Проверена`
                    : binding.status === 'draft'
                      ? t`Черновик`
                      : t`Отключена`}
                </Badge>
                {binding.status === 'draft' && onVerify ? (
                  <Button
                    disabled={pendingBindingId === binding.id}
                    onClick={() => onVerify(binding.id)}
                    size="xs"
                    variant="outline"
                  >
                    <Trans>Проверить</Trans>
                  </Button>
                ) : null}
                {binding.status !== 'disabled' && onDisable ? (
                  <Button
                    disabled={pendingBindingId === binding.id}
                    onClick={() => onDisable(binding.id)}
                    size="xs"
                    variant="ghost"
                  >
                    <Trans>Отключить</Trans>
                  </Button>
                ) : null}
                {binding.status === 'disabled' && onRestore ? (
                  <Button
                    disabled={pendingBindingId === binding.id}
                    onClick={() => onRestore(binding.id)}
                    size="xs"
                    variant="outline"
                  >
                    <Trans>Вернуть в черновик</Trans>
                  </Button>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
