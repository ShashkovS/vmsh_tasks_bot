import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Bell, Building2, CalendarClock, RefreshCw, UsersRound } from 'lucide-react'
import type { ReactNode } from 'react'

import {
  browserTimeZone,
  currentLocale,
  dateTimeFormat,
  DEFAULT_COURSE_TIME_ZONE,
  timeZoneShortName,
  zonesDifferAt,
} from '@vmsh/i18n'
import { Alert, AlertContent, AlertDescription, AlertTitle, Badge, Button, cn } from '@vmsh/ui'

export type ClassroomAssignmentPublicStatus = 'not_applicable' | 'reassigning' | 'assigned'

export interface ClassroomAssignmentStatusProps {
  audience: 'student' | 'family'
  status: ClassroomAssignmentPublicStatus
  startsAt?: string
  endsAt?: string
  classroomName?: string
  publishedAt?: string
  confirmedAt?: string
  announcedAt?: string
  studentName?: string
  /** Student-only action that opens the attendance-mode setting. */
  onlineModeAction?: ReactNode
  onOpenNotificationSettings?: () => void
  className?: string
}

function formatClassroomEventSchedule(startsAt?: string, endsAt?: string): string | null {
  if (!startsAt || !endsAt) return null
  const start = new Date(startsAt)
  const end = new Date(endsAt)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null
  // Shown in the viewer's zone; the course time follows when it differs
  // (vmshpwa/dev/ui-audit-20261104/BACKLOG.md, «Часовые пояса»).
  const viewer = browserTimeZone()
  const date = dateTimeFormat(currentLocale(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: viewer,
  }).format(start)
  const time = (timeZone: string) =>
    dateTimeFormat(currentLocale(), { hour: '2-digit', minute: '2-digit', timeZone })
  const own = `${date} · ${time(viewer).format(start)}–${time(viewer).format(end)}`
  if (!zonesDifferAt(start, viewer, DEFAULT_COURSE_TIME_ZONE)) return own
  const course = time(DEFAULT_COURSE_TIME_ZONE)
  return `${own} (${course.format(start)}–${course.format(end)} ${timeZoneShortName(DEFAULT_COURSE_TIME_ZONE, start)})`
}

/** Public Student/Family classroom projection; Staff planning stays in classroom-planning.tsx. */
export function ClassroomAssignmentStatus({
  audience,
  status,
  startsAt,
  endsAt,
  classroomName,
  publishedAt,
  confirmedAt,
  announcedAt,
  studentName,
  onlineModeAction,
  onOpenNotificationSettings,
  className,
}: ClassroomAssignmentStatusProps) {
  const eventSchedule = formatClassroomEventSchedule(startsAt, endsAt)
  const familyStudentName = studentName ?? t`ребёнок`
  if (status === 'reassigning') {
    return (
      <Alert className={className} role="status" tone="warning">
        <RefreshCw aria-hidden="true" />
        <AlertContent>
          <AlertTitle>
            <Trans>Аудитория переназначается</Trans>
          </AlertTitle>
          <AlertDescription>
            {audience === 'student'
              ? t`Прежняя аудитория больше не действует. Новая появится здесь после подтверждения.`
              : t`Прежняя аудитория ребёнка больше не действует. Новая появится после подтверждения.`}
          </AlertDescription>
          {eventSchedule ? (
            <p className="mt-1 flex items-center gap-1 text-small font-medium text-foreground">
              <CalendarClock aria-hidden="true" className="size-4" />
              {eventSchedule}
            </p>
          ) : null}
          {publishedAt ? (
            <p className="mt-1 text-caption text-muted-foreground">
              <Trans>Обновлено {publishedAt}</Trans>
            </p>
          ) : null}
          {audience === 'student' && onOpenNotificationSettings ? (
            <Button
              className="mt-2"
              onClick={onOpenNotificationSettings}
              size="xs"
              variant="outline"
            >
              <Bell aria-hidden="true" />
              <Trans>Настроить уведомления</Trans>
            </Button>
          ) : null}
        </AlertContent>
      </Alert>
    )
  }

  if (status === 'not_applicable') {
    return (
      <Alert className={className} tone="neutral">
        <UsersRound aria-hidden="true" />
        <AlertContent>
          {audience === 'student' ? (
            <AlertDescription>
              <Trans>Сейчас у вас онлайн-режим.</Trans> {onlineModeAction}
            </AlertDescription>
          ) : (
            <>
              <AlertTitle>
                <Trans>Очная аудитория не требуется</Trans>
              </AlertTitle>
              <AlertDescription>
                {studentName
                  ? t`${studentName}: сейчас онлайн-режим.`
                  : t`Сейчас у ребёнка онлайн-режим.`}
              </AlertDescription>
            </>
          )}
          {eventSchedule ? (
            <p className="mt-1 flex items-center gap-1 text-small font-medium text-foreground">
              <CalendarClock aria-hidden="true" className="size-4" />
              {eventSchedule}
            </p>
          ) : null}
        </AlertContent>
      </Alert>
    )
  }

  return (
    <section
      aria-label={audience === 'student' ? t`Ваша аудитория` : t`Аудитория ребёнка`}
      className={cn('rounded-md border border-border bg-surface p-4', className)}
    >
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-surface-sunken p-2 text-primary">
          <Building2 aria-hidden="true" className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-caption text-muted-foreground">
            {audience === 'student' ? t`Ваша аудитория` : t`Аудитория: ${familyStudentName}`}
          </p>
          {eventSchedule ? (
            <p className="mt-1 flex items-center gap-1 text-small font-medium text-foreground">
              <CalendarClock aria-hidden="true" className="size-4" />
              {eventSchedule}
            </p>
          ) : null}
          <p className="text-title font-semibold text-foreground">
            {classroomName ?? t`Название уточняется`}
          </p>
          {publishedAt ? (
            <p className="mt-1 text-caption text-muted-foreground">
              <Trans>Опубликовано {publishedAt}</Trans>
            </p>
          ) : null}
          {confirmedAt ? (
            <p className="mt-1 text-caption text-muted-foreground">
              <Trans>Подтверждено {confirmedAt}</Trans>
            </p>
          ) : null}
          {announcedAt ? (
            <p className="mt-1 text-caption text-muted-foreground">
              <Trans>Разослано {announcedAt}</Trans>
            </p>
          ) : null}
        </div>
        <Badge variant="success">
          <Trans>Назначена</Trans>
        </Badge>
      </div>
      {audience === 'student' && onOpenNotificationSettings ? (
        <Button className="mt-3" onClick={onOpenNotificationSettings} size="xs" variant="ghost">
          <Bell aria-hidden="true" />
          <Trans>Уведомления об изменениях</Trans>
        </Button>
      ) : null}
    </section>
  )
}
