import { useSyncExternalStore } from 'react'

import {
  CourseNetworkError,
  TestSubmissionNetworkError,
  type CourseRequestOptions,
  type StudentCourseClient,
  type StudentLessonListOptions,
  type TestSubmissionClient,
  type TestSubmissionRequestOptions,
} from '@vmsh/app-shell'
import {
  ContentNetworkError,
  type ContentApiClient,
  type ContentRequestOptions,
  type PublishedContentInput,
} from '@vmsh/content'
import {
  courseEnrollmentSchema,
  publishedContentSchema,
  studentCourseAccessResponseSchema,
  studentHomeResponseSchema,
  studentLessonListResponseSchema,
  studentLessonSummarySchema,
  studentProblemListResponseSchema,
  studentProblemRevealSchema,
  testAnswerInputResponseSchema,
  type CourseEnrollment,
  type PublishedContent,
  type StudentCourseAccessResponse,
  type StudentHomeResponse,
  type StudentLessonListResponse,
  type StudentLessonSummary,
  type StudentProblemListResponse,
  type StudentProblemReveal,
  type StudentRevealKind,
  type TestAnswerInputResponse,
} from '@vmsh/contracts'
import {
  readOfflineDocument,
  writeOfflineDocument,
  type OfflineDocumentDescriptor,
  type VmshOfflineDatabase,
} from '@vmsh/offline'

/**
 * Student transport decorator for Phase 3 cold-offline reading. Network/API
 * authorization stays in the existing clients; IndexedDB is only a fallback
 * for a network failure and is always scoped to the authenticated account.
 * See `dev/development-plan/07-phase-3-student-reading.md`.
 */

interface PayloadParser<T> {
  parse(payload: unknown): T
}

export interface StudentOfflineReadStatus {
  ownerId: string
  kind: OfflineDocumentDescriptor['kind']
  fetchedAt: string
  expiresAt: string
  stale: boolean
}

let currentOfflineRead: StudentOfflineReadStatus | null = null
const offlineReadListeners = new Set<() => void>()

function updateOfflineRead(status: StudentOfflineReadStatus | null): void {
  currentOfflineRead = status
  offlineReadListeners.forEach((listener) => listener())
}

export function useStudentOfflineReadStatus(): StudentOfflineReadStatus | null {
  return useSyncExternalStore(
    (listener) => {
      offlineReadListeners.add(listener)
      return () => offlineReadListeners.delete(listener)
    },
    () => currentOfflineRead,
    () => null,
  )
}

async function persistSuccessfulRead<T>(
  database: VmshOfflineDatabase,
  descriptor: OfflineDocumentDescriptor,
  version: string,
  payload: T,
  parser: PayloadParser<T>,
): Promise<void> {
  try {
    await writeOfflineDocument(database, descriptor, version, payload, parser)
  } catch {
    // A read cache is best-effort: an IndexedDB quota/close failure must not
    // replace a valid authoritative server response with an error page.
  }
}

async function readThroughCache<T>(input: {
  database: VmshOfflineDatabase
  descriptor: OfflineDocumentDescriptor
  parser: PayloadParser<T>
  request: () => Promise<T>
  version: (payload: T) => string
  isNetworkError: (error: unknown) => boolean
  allowOfflineFallback?: boolean
}): Promise<T> {
  try {
    const payload = await input.request()
    await persistSuccessfulRead(
      input.database,
      input.descriptor,
      input.version(payload),
      payload,
      input.parser,
    )
    updateOfflineRead(null)
    return payload
  } catch (error) {
    if (!input.isNetworkError(error)) throw error
    if (input.allowOfflineFallback === false) throw error
    const cached = await readOfflineDocument(input.database, input.descriptor, input.parser)
    if (!cached) throw error
    updateOfflineRead({
      ownerId: input.descriptor.ownerId,
      kind: input.descriptor.kind,
      fetchedAt: cached.fetchedAt,
      expiresAt: cached.expiresAt,
      stale: cached.stale,
    })
    return cached.data
  }
}

function descriptor(
  ownerId: string,
  kind: OfflineDocumentDescriptor['kind'],
  ...resourceParts: string[]
): OfflineDocumentDescriptor {
  return { ownerId, kind, resourceParts }
}

function lessonListVersion(payload: StudentLessonListResponse): string {
  const newest = payload.lessons[0]
  return newest
    ? `${newest.groupLessonId}:${newest.version}:${payload.lessons.length}:${payload.nextCursor ?? 'end'}`
    : `${payload.courseId}:${payload.groupId}:empty:${payload.nextCursor ?? 'end'}`
}

function accessVersion(payload: StudentCourseAccessResponse): string {
  const versions = payload.enrollments.map((enrollment) => enrollment.version)
  return `${payload.studentId}:${Math.max(0, ...versions)}:${payload.enrollments.length}`
}

export function createOfflineStudentCourseClient(
  online: StudentCourseClient,
  database: VmshOfflineDatabase,
  ownerId: string,
): StudentCourseClient {
  return {
    runtime: online.runtime,

    home(options: CourseRequestOptions = {}): Promise<StudentHomeResponse> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'student-home', 'current'),
        parser: studentHomeResponseSchema,
        request: () => online.home(options),
        version: (payload) => payload.generatedAt,
        isNetworkError: (error) => error instanceof CourseNetworkError,
      })
    },

    list(options: CourseRequestOptions = {}): Promise<StudentCourseAccessResponse> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'student-course-access', 'current'),
        parser: studentCourseAccessResponseSchema,
        request: () => online.list(options),
        version: accessVersion,
        isNetworkError: (error) => error instanceof CourseNetworkError,
      })
    },

    enrollment(courseId: string, options: CourseRequestOptions = {}): Promise<CourseEnrollment> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'student-course-enrollment', courseId),
        parser: courseEnrollmentSchema,
        request: () => online.enrollment(courseId, options),
        version: (payload) => String(payload.version),
        isNetworkError: (error) => error instanceof CourseNetworkError,
      })
    },

    lessons(
      courseId: string,
      options: StudentLessonListOptions = {},
    ): Promise<StudentLessonListResponse> {
      return readThroughCache({
        database,
        descriptor: descriptor(
          ownerId,
          'student-lesson-list',
          courseId,
          options.groupId ?? 'active-group',
          options.cursor ?? 'first-page',
        ),
        parser: studentLessonListResponseSchema,
        request: () => online.lessons(courseId, options),
        version: lessonListVersion,
        isNetworkError: (error) => error instanceof CourseNetworkError,
      })
    },

    lesson(
      courseId: string,
      groupLessonId: string,
      options: CourseRequestOptions = {},
    ): Promise<StudentLessonSummary> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'student-lesson', courseId, groupLessonId),
        parser: studentLessonSummarySchema,
        request: () => online.lesson(courseId, groupLessonId, options),
        version: (payload) => String(payload.version),
        isNetworkError: (error) => error instanceof CourseNetworkError,
      })
    },

    problems(
      courseId: string,
      groupLessonId: string,
      options: CourseRequestOptions = {},
    ): Promise<StudentProblemListResponse> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'student-problem-list', courseId, groupLessonId),
        parser: studentProblemListResponseSchema,
        request: () => online.problems(courseId, groupLessonId, options),
        version: (payload) => payload.conditionRevisionId,
        isNetworkError: (error) => error instanceof CourseNetworkError,
      })
    },
  }
}

export type StudentTestAnswerInputClient = Pick<TestSubmissionClient, 'input'>

export function createOfflineStudentTestAnswerInputClient(
  online: StudentTestAnswerInputClient,
  database: VmshOfflineDatabase,
  ownerId: string,
): StudentTestAnswerInputClient {
  return {
    input(
      problemId: string,
      options: TestSubmissionRequestOptions = {},
    ): Promise<TestAnswerInputResponse> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'student-test-answer-input', problemId),
        parser: testAnswerInputResponseSchema,
        request: () => online.input(problemId, options),
        version: (payload) =>
          `${payload.problemRevision.conditionRevisionId}:${payload.problemRevision.configVersion}`,
        isNetworkError: (error) => error instanceof TestSubmissionNetworkError,
      })
    },
  }
}

export type StudentPublishedContentClient = Pick<ContentApiClient, 'audience' | 'published'>

export function createOfflineStudentPublishedContentClient(
  online: ContentApiClient,
  database: VmshOfflineDatabase,
  ownerId: string,
): StudentPublishedContentClient {
  if (online.audience !== 'student') {
    throw new TypeError('Student offline content requires the Student audience')
  }
  return {
    audience: online.audience,
    published(
      input: PublishedContentInput,
      options: ContentRequestOptions = {},
    ): Promise<PublishedContent> {
      return readThroughCache({
        database,
        descriptor: descriptor(ownerId, 'published-content', input.groupLessonId, input.kind),
        parser: publishedContentSchema,
        request: () => online.published(input, options),
        version: (payload) => payload.revisionId,
        isNetworkError: (error) => error instanceof ContentNetworkError,
      })
    },
  }
}

function revealDescriptor(
  ownerId: string,
  groupLessonId: string,
  problemId: string,
  kind: StudentRevealKind,
) {
  return descriptor(ownerId, 'student-material-reveal', groupLessonId, problemId, kind)
}

export async function readCachedStudentProblemReveal(
  database: VmshOfflineDatabase,
  ownerId: string,
  input: { groupLessonId: string; problemId: string; kind: StudentRevealKind },
): Promise<StudentProblemReveal | null> {
  return (
    (
      await readOfflineDocument(
        database,
        revealDescriptor(ownerId, input.groupLessonId, input.problemId, input.kind),
        studentProblemRevealSchema,
      )
    )?.data ?? null
  )
}

export async function revealStudentProblemMaterialWithOfflineCache(
  online: ContentApiClient,
  database: VmshOfflineDatabase,
  ownerId: string,
  input: { groupLessonId: string; problemId: string; kind: StudentRevealKind },
  previouslyRevealed: boolean,
  options: ContentRequestOptions = {},
): Promise<StudentProblemReveal> {
  return readThroughCache({
    database,
    descriptor: revealDescriptor(ownerId, input.groupLessonId, input.problemId, input.kind),
    parser: studentProblemRevealSchema,
    request: () => online.revealStudentProblemMaterial(input, options),
    version: (payload) => payload.revisionId,
    isNetworkError: (error) => error instanceof ContentNetworkError,
    // A cached reveal belongs to the publication represented by the problem
    // projection that marked it revealed. If a replacement publication resets
    // the status to `available`, an older local copy must never reveal it.
    allowOfflineFallback: previouslyRevealed,
  })
}
