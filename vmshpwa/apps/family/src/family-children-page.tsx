import { useNavigate } from '@tanstack/react-router'
import { MapPin, Radio } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createFamilyCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useFamilyChildHomeQuery,
  useFamilyEnrollmentMutation,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type AttendanceMode,
  type CourseEnrollment,
  type CourseProgressResponse,
  type FamilyEnrollmentUpdateRequest,
} from '@vmsh/contracts'
import { ActivityCalendar, LevelChip, courseAchievementLabel, type GroupView } from '@vmsh/product'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

type ColorIndex = 0 | 1 | 2 | 3 | 4

function presentationIndex(token: string, fallback: number): ColorIndex {
  const suffix = /(?:^|[_-])([0-4])$/.exec(token)?.[1]
  if (suffix !== undefined) return Number(suffix) as ColorIndex
  return (((Math.max(1, fallback) - 1) % 4) + 1) as ColorIndex
}

function activeGroup(enrollment: CourseEnrollment): GroupView | undefined {
  const group = enrollment.allowedGroups.find(
    (candidate) => candidate.groupId === enrollment.activeGroupId,
  )
  if (!group) return undefined
  return {
    id: group.groupId,
    courseId: group.courseId,
    code: group.code,
    name: group.name,
    colorIndex: presentationIndex(group.colorKey, group.sortOrder),
  }
}

/** Family sees the same calm, course-scoped achievements as the child, never a rank. */
export function FamilyCourseAchievements({
  achievements,
}: {
  achievements: CourseProgressResponse['achievements']
}) {
  const visible = achievements.flatMap((achievement) => {
    const label = courseAchievementLabel(achievement.code)
    return label === undefined ? [] : [{ code: achievement.code, label }]
  })
  if (visible.length === 0) return null

  return (
    <section aria-label="Достижения курса" className="space-y-2">
      <p className="text-caption font-medium text-foreground">Достижения</p>
      <ul className="flex flex-wrap gap-2">
        {visible.map((achievement) => (
          <li key={achievement.code}>
            <Badge variant="outline">{achievement.label}</Badge>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function FamilyEnrollmentSettings({
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
    <div className="space-y-3 rounded-md border border-border bg-surface-subtle p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-small font-medium">
          <span>Группа</span>
          <select
            className="min-h-9 w-full rounded-md border border-input bg-surface px-3"
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
            className="min-h-9 w-full rounded-md border border-input bg-surface px-3"
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
          При очном формате организаторы резервируют место, печатают условия и распределяют
          преподавателей. Если ребёнок не придёт, выберите онлайн.
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

/** Production list of children from the revalidated Family principal. */
export function FamilyChildrenPage() {
  const principal = useAuthenticatedPrincipal()
  const navigate = useNavigate()
  if (principal.audience !== 'family') {
    throw new Error('Family children require a Family principal')
  }

  return (
    <PageLayout
      description="Связи создаёт администратор при регистрации. Данные разных детей не смешиваются."
      title="Дети"
    >
      {principal.linkedChildren.length === 0 ? (
        <PageStatePanel
          description="Обратитесь к администратору кружка, чтобы связать аккаунт с ребёнком."
          state="empty"
          title="Нет связанных детей"
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {principal.linkedChildren.map((child) => (
            <Card key={child.studentId}>
              <CardContent className="space-y-3 pt-5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <CardTitle>{child.displayName}</CardTitle>
                    {child.relationshipLabel ? (
                      <p className="text-small text-muted-foreground">{child.relationshipLabel}</p>
                    ) : null}
                  </div>
                  {child.isPrimary ? <Badge variant="outline">Основной профиль</Badge> : null}
                </div>
                <Button
                  className="w-full"
                  onClick={() =>
                    void navigate({
                      to: '/children/$childId',
                      params: { childId: child.studentId },
                    })
                  }
                  size="sm"
                  variant="outline"
                >
                  Открыть
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </PageLayout>
  )
}

/** Production per-child course context for Phase 9. */
export function FamilyChildPage({ childId }: { childId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const navigate = useNavigate()
  if (principal.audience !== 'family') {
    throw new Error('Family child page requires a Family principal')
  }
  const linkedChild = principal.linkedChildren.find((child) => child.studentId === childId)
  const requestedChildId = linkedChild?.studentId ?? 'missing'
  const childNumber = principal.linkedChildren.findIndex((child) => child.studentId === childId) + 1
  const client = useMemo(
    () =>
      createFamilyCourseClient(authentication.client.runtime, {
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
  const query = useFamilyChildHomeQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    requestedChildId,
    linkedChild !== undefined,
  )
  const enrollmentMutation = useFamilyEnrollmentMutation(
    client,
    { audience: 'family', accountId: principal.accountId },
    requestedChildId,
  )

  if (!linkedChild) {
    return (
      <PageLayout title="Ребёнок">
        <PageStatePanel
          description="Этот профиль не связан с вашей учётной записью."
          state="forbidden"
        />
      </PageLayout>
    )
  }
  if (query.isPending) {
    return (
      <PageLayout title={linkedChild.displayName}>
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    const forbidden = query.error instanceof ApiResponseError && query.error.status === 403
    return (
      <PageLayout title={linkedChild.displayName}>
        <PageStatePanel
          {...(!forbidden
            ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
            : {})}
          state={forbidden ? 'forbidden' : 'error'}
        />
      </PageLayout>
    )
  }

  const student = query.data.student
  return (
    <PageLayout
      description="Режим и активная группа показаны отдельно для каждого курса."
      eyebrow={student.grade === null ? undefined : `${student.grade} класс`}
      title={student.displayName}
    >
      {query.data.courses.length === 0 ? (
        <PageStatePanel
          description="Когда ребёнка добавят на курс, он появится здесь."
          state="empty"
          title="Нет активных курсов"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {query.data.courses.map(({ enrollment, currentLesson, progress }) => {
            const group = activeGroup(enrollment)
            const inPerson = enrollment.attendanceMode === 'in_person'
            return (
              <Card key={enrollment.enrollmentId}>
                <CardHeader className="gap-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-caption text-muted-foreground">
                        {enrollment.course.subjectCode}
                      </p>
                      <CardTitle>{enrollment.course.name}</CardTitle>
                    </div>
                    <Badge variant={inPerson ? 'info' : 'neutral'}>
                      {inPerson ? <MapPin aria-hidden="true" /> : <Radio aria-hidden="true" />}
                      {inPerson ? 'Очно' : 'Онлайн'}
                    </Badge>
                  </div>
                  {group ? <LevelChip level={group} /> : null}
                </CardHeader>
                <CardContent className="space-y-3">
                  {currentLesson ? (
                    <div className="space-y-1">
                      <p className="text-small font-medium text-foreground">
                        Занятие {currentLesson.lessonNumber} · {currentLesson.title}
                      </p>
                      <p className="text-caption text-muted-foreground">
                        {currentLesson.problemCount} задач в листке
                      </p>
                    </div>
                  ) : (
                    <p className="text-small text-muted-foreground">
                      Новое занятие пока не опубликовано
                    </p>
                  )}
                  <p className="text-small text-muted-foreground">
                    {progress.summary.accepted} зачтено из {progress.summary.attempted} задач
                    {progress.summary.awaitingReview > 0
                      ? ` · ждут проверки: ${progress.summary.awaitingReview}`
                      : ''}
                  </p>
                  <FamilyCourseAchievements achievements={progress.achievements} />
                  {progress.lessons.length || progress.activity.length ? (
                    <details className="rounded-md border border-border bg-surface px-3 py-2">
                      <summary className="cursor-pointer text-small font-medium">
                        История курса
                      </summary>
                      <div className="mt-3 space-y-4">
                        {progress.lessons.length ? (
                          <ul className="divide-y divide-border text-small">
                            {progress.lessons.map((lesson) => (
                              <li
                                className="flex items-center justify-between gap-3 py-2"
                                key={lesson.lessonNumber}
                              >
                                <span>Занятие {lesson.lessonNumber}</span>
                                <span className="text-muted-foreground">
                                  {lesson.accepted} из {lesson.attempted} зачтено
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        <ActivityCalendar days={progress.activity} />
                      </div>
                    </details>
                  ) : null}
                  <FamilyEnrollmentSettings
                    enrollment={enrollment}
                    error={
                      enrollmentMutation.isError &&
                      enrollmentMutation.variables?.courseId === enrollment.course.courseId
                    }
                    onSave={(input) =>
                      enrollmentMutation.mutateAsync({
                        courseId: enrollment.course.courseId,
                        input,
                      })
                    }
                    saving={
                      enrollmentMutation.isPending &&
                      enrollmentMutation.variables?.courseId === enrollment.course.courseId
                    }
                    key={`${enrollment.enrollmentId}:${enrollment.version}`}
                  />
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-caption text-muted-foreground">
                      Доступно групп: {enrollment.allowedGroups.length}
                    </p>
                    {currentLesson ? (
                      <Button
                        onClick={() =>
                          void navigate({
                            to: '/tasks/$courseCode/$groupCode/$lessonNumber',
                            params: {
                              courseCode: enrollment.course.code,
                              groupCode: group?.code ?? '',
                              lessonNumber: String(currentLesson.lessonNumber),
                            },
                            search:
                              principal.linkedChildren.length > 1 ? { child: childNumber } : {},
                          })
                        }
                        disabled={!group}
                        size="sm"
                        variant="outline"
                      >
                        Открыть листок
                      </Button>
                    ) : null}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </PageLayout>
  )
}
