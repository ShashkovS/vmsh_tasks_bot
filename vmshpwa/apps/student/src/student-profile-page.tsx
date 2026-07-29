import { useMemo, useState } from 'react'

import {
  AccountSessionManager,
  CourseNetworkError,
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
  const [groupId, setGroupId] = useState(enrollment.activeGroupId)
  const [mode, setMode] = useState<AttendanceMode>(enrollment.attendanceMode)
  const [reviewing, setReviewing] = useState(false)
  const changed = groupId !== enrollment.activeGroupId || mode !== enrollment.attendanceMode

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-small font-medium">
          <span>Активная группа</span>
          <select
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
        </label>
        <label className="space-y-1 text-small font-medium">
          <span>Формат занятий</span>
          <select
            className="min-h-10 w-full rounded-md border border-input bg-surface px-3"
            disabled={saving}
            onChange={(event) => {
              setMode(event.target.value as AttendanceMode)
              setReviewing(false)
            }}
            value={mode}
          >
            <option value="online">Онлайн</option>
            <option value="in_person">Очно в школе</option>
          </select>
        </label>
      </div>
      {reviewing ? (
        <p className="text-small text-muted-foreground">
          При очном формате для вас резервируют место, печатают условия и распределяют
          преподавателей. Если вы не придёте, выберите онлайн.
        </p>
      ) : null}
      {error ? (
        <p className="text-small text-status-error" role="alert">
          Не удалось сохранить. Обновите страницу и попробуйте ещё раз.
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
        {saving ? 'Сохраняем…' : reviewing ? 'Подтвердить изменения' : 'Изменить'}
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
      <PageLayout title="Профиль">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (courses.error) {
    return (
      <PageLayout title="Профиль">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void courses.refetch()}
          state={courses.error instanceof CourseNetworkError ? 'offline' : 'error'}
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description="Группа и формат задаются отдельно для каждого курса."
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
        <AccountSessionManager title="Устройства и сеансы" />
        <Card>
          <CardHeader>
            <CardTitle>Помощь</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-small">
            <a className="text-link underline-offset-2 hover:underline" href="/student/questions">
              Мои вопросы
            </a>
            <br />
            <a className="text-link underline-offset-2 hover:underline" href="mailto:vmsh@179.ru">
              vmsh@179.ru
            </a>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  )
}
