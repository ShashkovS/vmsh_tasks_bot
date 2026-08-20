import { useNavigate } from '@tanstack/react-router'
import { BookOpen, MapPin, Radio } from 'lucide-react'
import { useMemo } from 'react'

import {
  CourseNetworkError,
  PublishedClassroomNetworkError,
  PageLayout,
  PageSection,
  PageStatePanel,
  bannerDismissalId,
  createGroupBannerClient,
  createStudentCourseClient,
  createStudentClassroomAssignmentClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useActiveGroupBannersQuery,
  useBannerDismissals,
  useStudentHomeQuery,
  usePublishedClassroomAssignmentsQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type StudentHomeCourse } from '@vmsh/contracts'
import { useOfflineDatabase } from '@vmsh/offline'
import { ClassroomAssignmentStatus, CourseCard, GroupBanner, LevelChip } from '@vmsh/product'
import { Badge, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

import {
  formatCalendarDate,
  problemCountLabel,
  studentPhaseLabel,
  toCourseEnrollmentView,
} from './student-home-view'
import { createOfflineStudentCourseClient } from './offline-student-data'

function formatMoment(value: string | null): string | undefined {
  if (value === null) return undefined
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function EmptyCourseCard({ course }: { course: StudentHomeCourse }) {
  const enrollment = toCourseEnrollmentView(course.enrollment)
  const group = enrollment.allowedGroups.find(
    (candidate) => candidate.id === enrollment.activeGroupId,
  )
  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-caption text-muted-foreground">{enrollment.course.subjectCode}</p>
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
      <CardContent className="flex items-center gap-2 text-small text-muted-foreground">
        <BookOpen aria-hidden="true" className="size-4" />
        Новое занятие пока не опубликовано
      </CardContent>
    </Card>
  )
}

/** Production Student «Сейчас» over the authenticated Phase-3 home read model. */
export function StudentHomePage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') {
    throw new Error('Student home requires a Student principal')
  }
  const database = useOfflineDatabase()
  const client = useMemo(() => {
    const online = createStudentCourseClient(authentication.client.runtime, {
      refreshSession: async () => {
        try {
          return await authentication.refresh()
        } catch (error) {
          authentication.handleApiError(error)
          throw error
        }
      },
    })
    return createOfflineStudentCourseClient(online, database, principal.accountId)
  }, [authentication, database, principal.accountId])
  const query = useStudentHomeQuery(client, {
    audience: 'student',
    accountId: principal.accountId,
  })
  const principalScope = { audience: 'student' as const, accountId: principal.accountId }
  const bannerClient = useMemo(
    () =>
      createGroupBannerClient(authentication.client.runtime, 'student', {
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
  const bannerQuery = useActiveGroupBannersQuery(bannerClient, principalScope)
  const bannerDismissals = useBannerDismissals(principalScope)
  const classroomClient = useMemo(
    () =>
      createStudentClassroomAssignmentClient(authentication.client.runtime, {
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
  const classroomQuery = usePublishedClassroomAssignmentsQuery(classroomClient, {
    audience: 'student',
    accountId: principal.accountId,
  })
  const navigate = useNavigate()

  if (query.isPending) {
    return (
      <PageLayout title="Сейчас">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error) {
    const state =
      query.error instanceof CourseNetworkError
        ? 'offline'
        : query.error instanceof ApiResponseError && query.error.status === 403
          ? 'forbidden'
          : 'error'
    return (
      <PageLayout title="Сейчас">
        <PageStatePanel
          {...(state === 'error' || state === 'offline'
            ? { actionLabel: 'Повторить', onAction: () => void query.refetch() }
            : {})}
          state={state}
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout eyebrow="Ваши курсы" title="Сейчас">
      {bannerQuery.data ? (
        <div className="space-y-2" aria-label="Объявления">
          {bannerQuery.data.items
            .filter((banner) => !bannerDismissals.dismissed.has(bannerDismissalId(banner)))
            .map((banner) => (
              <GroupBanner
                banner={banner}
                key={banner.bannerId}
                onDismiss={() => bannerDismissals.dismiss(banner)}
              />
            ))}
        </div>
      ) : null}
      <PageSection title="Сейчас по курсам">
        {query.data.courses.length === 0 ? (
          <PageStatePanel
            description="Когда вас добавят на курс, он появится здесь."
            state="empty"
            title="Нет активных курсов"
          />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {query.data.courses.map((course) => {
              const classroom = classroomQuery.data?.items.find(
                (item) => item.coursePublicId === course.enrollment.course.courseId,
              )
              const activeGroup = course.enrollment.allowedGroups.find(
                (group) => group.groupId === course.enrollment.activeGroupId,
              )
              if (course.phase === 'no_lesson') {
                return <EmptyCourseCard course={course} key={course.enrollment.enrollmentId} />
              }
              const lesson = course.currentLesson
              return (
                <CourseCard
                  {...(classroom?.status === 'assigned' && classroom.classroomName
                    ? { classroomName: classroom.classroomName }
                    : {})}
                  enrollment={toCourseEnrollmentView(course.enrollment)}
                  key={course.enrollment.enrollmentId}
                  lessonDate={formatCalendarDate(lesson.cycleAnchorDate)}
                  lessonNumber={lesson.lessonNumber}
                  onOpen={() => {
                    if (!activeGroup) return
                    // One worksheet interface: the course opens the same Tasks
                    // feed as the menu entry, pre-filtered to this enrolment.
                    void navigate({
                      to: '/tasks',
                      search: {
                        course: course.enrollment.course.courseId,
                        group: activeGroup.groupId,
                      },
                    })
                  }}
                  phase={studentPhaseLabel(course)}
                  progressLabel={problemCountLabel(lesson.problemCount)}
                />
              )
            })}
          </div>
        )}
      </PageSection>
      <PageSection title="Очные занятия">
        {classroomQuery.isPending ? <PageStatePanel state="loading" /> : null}
        {classroomQuery.error ? (
          <PageStatePanel
            actionLabel="Повторить"
            onAction={() => void classroomQuery.refetch()}
            state={
              classroomQuery.error instanceof PublishedClassroomNetworkError ? 'offline' : 'error'
            }
          />
        ) : null}
        {classroomQuery.data?.items.length === 0 ? (
          <p className="text-small text-muted-foreground">
            Для ваших групп пока нет запланированных очных занятий.
          </p>
        ) : null}
        <div className="grid gap-3 lg:grid-cols-2">
          {classroomQuery.data?.items.map((item) => {
            const announcedAt = formatMoment(item.announcedAt)
            const confirmedAt = formatMoment(item.confirmedAt)
            return (
              <div className="space-y-2" key={`${item.eventPublicId}:${item.coursePublicId}`}>
                <p className="text-small font-medium text-foreground">
                  {item.courseName} · {item.eventName}
                </p>
                <ClassroomAssignmentStatus
                  {...(announcedAt ? { announcedAt } : {})}
                  audience="student"
                  {...(item.classroomName ? { classroomName: item.classroomName } : {})}
                  {...(confirmedAt ? { confirmedAt } : {})}
                  endsAt={item.endsAt}
                  startsAt={item.startsAt}
                  status={item.status}
                />
              </div>
            )
          })}
        </div>
      </PageSection>
    </PageLayout>
  )
}
