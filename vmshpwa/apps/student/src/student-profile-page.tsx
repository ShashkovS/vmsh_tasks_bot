import { t } from '@lingui/core/macro'
import { Trans, useLingui } from '@lingui/react/macro'
import { OrganizerLink } from '@vmsh/app-shell'
import { useMemo, useState } from 'react'
import { Mail, MessageCircleQuestion } from 'lucide-react'

import {
  AccountSessionManager,
  CourseNetworkError,
  InterfaceLanguageCard,
  PageLayout,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentCoursesQuery,
  useStudentEnrollmentMutation,
} from '@vmsh/app-shell'
import type {
  AttendanceMode,
  CourseEnrollment,
  FamilyEnrollmentUpdateRequest,
} from '@vmsh/contracts'
import { LevelChip, type GroupView } from '@vmsh/product'
import { Button, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

import { toCourseEnrollmentView } from './student-home-view'

function activeGroup(enrollment: CourseEnrollment): GroupView | undefined {
  const view = toCourseEnrollmentView(enrollment)
  return view.allowedGroups.find((group) => group.id === view.activeGroupId)
}

export function StudentEnrollmentSettings({
  enrollment,
  error,
  saving,
  onSave,
}: {
  enrollment: CourseEnrollment
  error: boolean
  saving: boolean
  onSave: (input: FamilyEnrollmentUpdateRequest) => Promise<unknown>
}) {
  const { t } = useLingui()
  const [groupId, setGroupId] = useState(enrollment.activeGroupId)
  const [mode, setMode] = useState<AttendanceMode>(enrollment.attendanceMode)
  const [reviewing, setReviewing] = useState(false)
  const changed = groupId !== enrollment.activeGroupId || mode !== enrollment.attendanceMode

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1 text-small font-medium">
          <span>
            <Trans>Активная группа</Trans>
          </span>
          <select
            aria-label={t`Активная группа`}
            className="min-h-10 w-full rounded-md border border-input bg-surface px-3"
            disabled={saving}
            onChange={(event) => {
              setGroupId(event.target.value)
              setReviewing(false)
            }}
            value={groupId}
          >
            {enrollment.allowedGroups.map((group) => (
              <option key={group.groupId} value={group.groupId}>
                {group.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1 text-small font-medium">
          <span>
            <Trans>Формат занятий</Trans>
          </span>
          <select
            aria-label={t`Формат занятий`}
            className="min-h-10 w-full rounded-md border border-input bg-surface px-3"
            disabled={saving}
            onChange={(event) => {
              setMode(event.target.value as AttendanceMode)
              setReviewing(false)
            }}
            value={mode}
          >
            <option value="online">
              <Trans>Онлайн</Trans>
            </option>
            <option value="in_person">
              <Trans>Очно в школе</Trans>
            </option>
          </select>
        </div>
      </div>
      {reviewing ? (
        <p className="text-small text-muted-foreground">
          <Trans>
            При очном формате для вас резервируют место, печатают условия и распределяют
            преподавателей. Если вы не придёте, выберите онлайн.
          </Trans>
        </p>
      ) : null}
      {error ? (
        <p className="text-small text-status-error" role="alert">
          <Trans>Не удалось сохранить. Обновите страницу и попробуйте ещё раз.</Trans>
        </p>
      ) : null}
      <Button
        disabled={!changed || saving}
        onClick={() => {
          if (!reviewing) {
            setReviewing(true)
            return
          }
          void onSave({
            activeGroupId: groupId,
            attendanceMode: mode,
            version: enrollment.version,
          }).catch(() => undefined)
        }}
        size="sm"
        variant={reviewing ? 'default' : 'outline'}
      >
        {saving ? t`Сохраняем…` : reviewing ? t`Подтвердить изменения` : t`Изменить`}
      </Button>
    </div>
  )
}

/** Real Student profile for Phase 3 and Phase 9 course settings. */
export function StudentProfilePage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student profile requires Student')
  const client = useMemo(
    () =>
      createStudentCourseClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const scope = { audience: 'student' as const, accountId: principal.accountId }
  const courses = useStudentCoursesQuery(client, scope)
  const mutation = useStudentEnrollmentMutation(client, scope)

  if (courses.isPending) {
    return (
      <PageLayout title={t`Профиль`}>
        <OrganizerLink />
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (courses.error) {
    return (
      <PageLayout title={t`Профиль`}>
        <OrganizerLink />
        <PageStatePanel
          actionLabel={t`Повторить`}
          onAction={() => void courses.refetch()}
          state={courses.error instanceof CourseNetworkError ? 'offline' : 'error'}
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description={t`Группа и формат задаются отдельно для каждого курса.`}
      title={principal.displayName}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {courses.data.enrollments.map((enrollment) => {
          const group = activeGroup(enrollment)
          const currentMutation = mutation.variables?.courseId === enrollment.course.courseId
          return (
            <Card key={enrollment.enrollmentId}>
              <CardHeader className="gap-2">
                <CardTitle>{enrollment.course.name}</CardTitle>
                {group ? <LevelChip level={group} /> : null}
              </CardHeader>
              <CardContent>
                <StudentEnrollmentSettings
                  enrollment={enrollment}
                  error={mutation.isError && currentMutation}
                  key={`${enrollment.enrollmentId}:${enrollment.version}`}
                  onSave={(input) =>
                    mutation.mutateAsync({ courseId: enrollment.course.courseId, input })
                  }
                  saving={mutation.isPending && currentMutation}
                />
              </CardContent>
            </Card>
          )
        })}
        <Card>
          <CardHeader>
            <CardTitle>
              <Trans>Уведомления</Trans>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-small text-muted-foreground">
              <Trans>Выберите, какие уведомления получать, и подключите это устройство.</Trans>
            </p>
            <a
              className="inline-flex min-h-10 items-center text-link underline underline-offset-2"
              href="/student/profile/notifications"
            >
              <Trans>Настроить уведомления</Trans>
            </a>
          </CardContent>
        </Card>
        <InterfaceLanguageCard />
        <AccountSessionManager title={t`Устройства и сеансы`} />
        <Card>
          <CardHeader>
            <CardTitle>
              <Trans>Помощь</Trans>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-x-5 gap-y-3 text-small">
            <OrganizerLink />
            <a
              className="inline-flex min-h-7 items-center gap-2 text-link underline-offset-2 hover:underline"
              href="/student/questions"
            >
              <MessageCircleQuestion aria-hidden="true" className="size-4 shrink-0" />
              <Trans>Мои вопросы</Trans>
            </a>
            <a
              className="inline-flex min-h-7 items-center gap-2 text-link underline-offset-2 hover:underline"
              href="mailto:vmsh@179.ru"
            >
              <Mail aria-hidden="true" className="size-4 shrink-0" />
              vmsh@179.ru
            </a>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
