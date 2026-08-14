import { useEffect, useMemo, useState } from 'react'

import {
  CourseNetworkError,
  PageLayout,
  PageStatePanel,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentCoursesQuery,
  useStudentLessonArchiveQuery,
  useStudentProblemsQuery,
} from '@vmsh/app-shell'
import { ApiResponseError } from '@vmsh/contracts'
import { useOfflineDatabase } from '@vmsh/offline'

import { createOfflineStudentCourseClient } from './offline-student-data'
import { CanonicalStudentTask, CanonicalStudentWorksheet } from './student-task-detail-page'

function ReadableRouteState({ error }: { error: unknown }) {
  const state =
    error instanceof CourseNetworkError
      ? 'offline'
      : error instanceof ApiResponseError && error.status === 403
        ? 'forbidden'
        : 'error'
  return <PageStatePanel state={state} />
}

export function StudentReadableTaskPage({
  courseCode,
  displayNumber,
  groupCode,
  lessonNumber,
}: {
  courseCode: string
  displayNumber?: string
  groupCode: string
  lessonNumber: number
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Student task requires Student auth')
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
  const access = useStudentCoursesQuery(client, {
    audience: 'student',
    accountId: principal.accountId,
  })

  if (access.isPending) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (access.error) {
    return (
      <PageLayout title="Листок" width="content">
        <ReadableRouteState error={access.error} />
      </PageLayout>
    )
  }
  const enrollment = access.data.enrollments.find(
    (candidate) =>
      candidate.course.code.toLocaleLowerCase('ru-RU') === courseCode.toLocaleLowerCase('ru-RU'),
  )
  const group = enrollment?.allowedGroups.find(
    (candidate) =>
      candidate.code.toLocaleLowerCase('ru-RU') === groupCode.toLocaleLowerCase('ru-RU'),
  )
  if (!enrollment || !group || !Number.isInteger(lessonNumber) || lessonNumber < 0) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel
          description="Проверьте код курса, группы и номер занятия в ссылке."
          state="empty"
          title="Листок не найден"
        />
      </PageLayout>
    )
  }
  return (
    <ReadableLesson
      client={client}
      courseId={enrollment.course.courseId}
      {...(displayNumber ? { displayNumber } : {})}
      groupId={group.groupId}
      lessonNumber={lessonNumber}
      principal={{ audience: 'student', accountId: principal.accountId }}
    />
  )
}

function ReadableLesson({
  client,
  courseId,
  displayNumber,
  groupId,
  lessonNumber,
  principal,
}: {
  client: ReturnType<typeof createOfflineStudentCourseClient>
  courseId: string
  displayNumber?: string
  groupId: string
  lessonNumber: number
  principal: { audience: 'student'; accountId: string }
}) {
  const [openedAt] = useState(() => Date.now())
  const archive = useStudentLessonArchiveQuery(client, principal, courseId, groupId)
  const lesson = archive.data?.pages
    .flatMap((page) => page.lessons)
    .find((candidate) => candidate.lessonNumber === lessonNumber)

  useEffect(() => {
    if (!lesson && archive.hasNextPage && !archive.isFetchingNextPage) {
      void archive.fetchNextPage()
    }
  }, [archive, lesson])

  if (archive.isPending || (!lesson && archive.hasNextPage)) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (archive.error) {
    return (
      <PageLayout title="Листок" width="content">
        <ReadableRouteState error={archive.error} />
      </PageLayout>
    )
  }
  if (!lesson) {
    return (
      <PageLayout title="Листок" width="content">
        <PageStatePanel state="empty" title="Занятие ещё не опубликовано" />
      </PageLayout>
    )
  }
  if (!displayNumber) {
    const submissionClosed = lesson.window
      ? openedAt >= Date.parse(lesson.window.submissionClosesAt)
      : false
    return (
      <CanonicalStudentWorksheet
        courseId={courseId}
        displayTitle={
          lesson.title?.trim()
            ? `Занятие ${lesson.lessonNumber} · ${lesson.title.trim()}`
            : `Занятие ${lesson.lessonNumber}`
        }
        groupId={groupId}
        groupLessonId={lesson.groupLessonId}
        submissionClosed={submissionClosed}
        taskId={`lesson-${lessonNumber}`}
      />
    )
  }
  return (
    <ReadableProblem
      client={client}
      courseId={courseId}
      displayNumber={displayNumber}
      groupId={groupId}
      groupLessonId={lesson.groupLessonId}
      submissionClosed={
        lesson.window ? openedAt >= Date.parse(lesson.window.submissionClosesAt) : false
      }
      principal={principal}
    />
  )
}

function ReadableProblem({
  client,
  courseId,
  displayNumber,
  groupId,
  groupLessonId,
  principal,
  submissionClosed,
}: {
  client: ReturnType<typeof createOfflineStudentCourseClient>
  courseId: string
  displayNumber: string
  groupId: string
  groupLessonId: string
  principal: { audience: 'student'; accountId: string }
  submissionClosed: boolean
}) {
  const problems = useStudentProblemsQuery(client, principal, courseId, groupId, groupLessonId)
  if (problems.isPending) {
    return (
      <PageLayout title="Задача" width="reading">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (problems.error) {
    return (
      <PageLayout title="Задача" width="reading">
        <ReadableRouteState error={problems.error} />
      </PageLayout>
    )
  }
  const problem = problems.data.problems.find(
    (candidate) => candidate.displayNumber === displayNumber,
  )
  if (!problem) {
    return (
      <PageLayout title="Задача" width="reading">
        <PageStatePanel state="empty" title="Задача не найдена" />
      </PageLayout>
    )
  }
  return (
    <CanonicalStudentTask
      courseId={courseId}
      groupId={groupId}
      groupLessonId={groupLessonId}
      submissionClosed={submissionClosed}
      taskId={problem.problemId}
    />
  )
}
