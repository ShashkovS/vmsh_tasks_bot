import { useNavigate } from '@tanstack/react-router'
import { BookOpen, MapPin, Radio } from 'lucide-react'
import { useMemo } from 'react'

import {
  CourseNetworkError,
  PageLayout,
  PageSection,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentHomeQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type StudentHomeCourse } from '@vmsh/contracts'
import { useOfflineDatabase } from '@vmsh/offline'
import { CourseCard, LevelChip } from '@vmsh/product'
import { Badge, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

import {
  formatCalendarDate,
  problemCountLabel,
  studentPhaseLabel,
  toCourseEnrollmentView,
} from './student-home-view'
import { createOfflineStudentCourseClient } from './offline-student-data'

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
    <PageLayout
      description="У каждого курса своё занятие, расписание и режим участия."
      eyebrow="Ваши курсы"
      title="Сейчас"
    >
      <PageSection
        description="Показываем последнее опубликованное занятие активной группы каждого курса."
        title="Сейчас по курсам"
      >
        {query.data.courses.length === 0 ? (
          <PageStatePanel
            description="Когда вас добавят на курс, он появится здесь."
            state="empty"
            title="Нет активных курсов"
          />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {query.data.courses.map((course) => {
              if (course.phase === 'no_lesson') {
                return <EmptyCourseCard course={course} key={course.enrollment.enrollmentId} />
              }
              const lesson = course.currentLesson
              return (
                <CourseCard
                  enrollment={toCourseEnrollmentView(course.enrollment)}
                  key={course.enrollment.enrollmentId}
                  lessonDate={formatCalendarDate(lesson.cycleAnchorDate)}
                  lessonNumber={lesson.lessonNumber}
                  onOpen={() => {
                    void navigate({
                      to: '/tasks/$taskId',
                      params: { taskId: `lesson-${lesson.lessonNumber}` },
                      search: {
                        groupLesson: lesson.groupLessonId,
                        material: 'condition',
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
    </PageLayout>
  )
}
