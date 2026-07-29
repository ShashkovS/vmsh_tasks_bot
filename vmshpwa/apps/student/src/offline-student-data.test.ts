import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { CourseNetworkError, type StudentCourseClient } from '@vmsh/app-shell'
import { ContentNetworkError, type ContentApiClient } from '@vmsh/content'
import webDocumentFixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import studentProblemsFixture from '@vmsh/contracts/fixtures/courses/student-problems.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import {
  publishedContentSchema,
  runtimeConfigSchema,
  studentProblemListResponseSchema,
  studentProblemRevealSchema,
  webContentDocumentSchema,
} from '@vmsh/contracts'
import { VmshOfflineDatabase } from '@vmsh/offline'

import {
  createOfflineStudentCourseClient,
  createOfflineStudentPublishedContentClient,
  readCachedStudentProblemReveal,
  revealStudentProblemMaterialWithOfflineCache,
} from './offline-student-data'

const databases = new Set<VmshOfflineDatabase>()
const ownerId = 'account-student-fixture'
const problems = studentProblemListResponseSchema.parse(studentProblemsFixture.response)
const document = webContentDocumentSchema.parse(webDocumentFixture.document)
const published = publishedContentSchema.parse({
  groupLessonId: problems.groupLessonId,
  courseId: problems.courseId,
  groupId: problems.groupId,
  kind: 'condition',
  publicationId: 'publication-condition-fixture',
  publicationVersion: 1,
  publishedAt: '2026-07-28T10:00:00.000Z',
  revisionId: document.revisionId,
  document,
})
const hintDocument = {
  ...document,
  revisionId: 'revision-hint-fixture',
  materialKind: 'hint' as const,
  introduction: [],
  problems: [document.problems[0]],
}
const reveal = studentProblemRevealSchema.parse({
  groupLessonId: problems.groupLessonId,
  courseId: problems.courseId,
  groupId: problems.groupId,
  kind: 'hint',
  publicationId: 'publication-hint-fixture',
  publicationVersion: 1,
  publishedAt: '2026-07-28T10:00:00.000Z',
  revisionId: hintDocument.revisionId,
  problemId: problems.problems[0]?.problemId,
  sourceOrdinal: problems.problems[0]?.sourceOrdinal,
  revealedAt: '2026-07-28T10:05:00.000Z',
  firstReveal: true,
  document: hintDocument,
})

afterEach(async () => {
  await Promise.all(
    [...databases].map(async (database) => {
      database.close()
      await database.delete()
    }),
  )
  databases.clear()
})

function database(instance: string) {
  const value = new VmshOfflineDatabase({ audience: 'student', instance })
  databases.add(value)
  return value
}

function courseClient(problemsRequest: StudentCourseClient['problems']): StudentCourseClient {
  const unavailable = vi.fn(() => Promise.reject(new Error('unused')))
  return {
    runtime: runtimeConfigSchema.parse(runtimeFixture.response),
    home: unavailable,
    list: unavailable,
    enrollment: unavailable,
    updateEnrollment: unavailable,
    progress: unavailable,
    lessons: unavailable,
    lesson: unavailable,
    problems: problemsRequest,
  }
}

function contentClient(input: {
  published?: ContentApiClient['published']
  reveal?: ContentApiClient['revealStudentProblemMaterial']
}): ContentApiClient {
  return {
    audience: 'student',
    published: input.published ?? vi.fn(() => Promise.reject(new Error('unused'))),
    revealStudentProblemMaterial: input.reveal ?? vi.fn(() => Promise.reject(new Error('unused'))),
  } as ContentApiClient
}

describe('Student offline transport decorators', () => {
  it('writes a validated problem list and falls back only on a network failure', async () => {
    const target = database('student-problems')
    const onlineProblems = vi.fn().mockResolvedValueOnce(problems)
    const offline = createOfflineStudentCourseClient(courseClient(onlineProblems), target, ownerId)

    await expect(offline.problems(problems.courseId, problems.groupLessonId)).resolves.toEqual(
      problems,
    )
    onlineProblems.mockRejectedValueOnce(new CourseNetworkError({ cause: new Error('offline') }))
    await expect(offline.problems(problems.courseId, problems.groupLessonId)).resolves.toEqual(
      problems,
    )

    const forbidden = new Error('forbidden')
    onlineProblems.mockRejectedValueOnce(forbidden)
    await expect(offline.problems(problems.courseId, problems.groupLessonId)).rejects.toBe(
      forbidden,
    )
  })

  it('serves the last validated condition when the content transport is offline', async () => {
    const target = database('student-condition')
    const onlinePublished = vi.fn().mockResolvedValueOnce(published)
    const offline = createOfflineStudentPublishedContentClient(
      contentClient({ published: onlinePublished }),
      target,
      ownerId,
    )
    const request = { groupLessonId: problems.groupLessonId, kind: 'condition' as const }

    await expect(offline.published(request)).resolves.toEqual(published)
    onlinePublished.mockRejectedValueOnce(new ContentNetworkError({ cause: new Error('offline') }))
    await expect(offline.published(request)).resolves.toEqual(published)
  })

  it('never invents a reveal offline, but reopens one cached after a successful audit', async () => {
    const target = database('student-reveal')
    const revealRequest = {
      groupLessonId: reveal.groupLessonId,
      problemId: reveal.problemId,
      kind: reveal.kind,
    }
    const onlineReveal = vi
      .fn()
      .mockRejectedValueOnce(new ContentNetworkError({ cause: new Error('offline') }))
      .mockResolvedValueOnce(reveal)
      .mockRejectedValueOnce(new ContentNetworkError({ cause: new Error('offline') }))
    const online = contentClient({ reveal: onlineReveal })

    await expect(
      revealStudentProblemMaterialWithOfflineCache(online, target, ownerId, revealRequest, false),
    ).rejects.toBeInstanceOf(ContentNetworkError)
    await expect(readCachedStudentProblemReveal(target, ownerId, revealRequest)).resolves.toBeNull()

    await expect(
      revealStudentProblemMaterialWithOfflineCache(online, target, ownerId, revealRequest, false),
    ).resolves.toEqual(reveal)
    await expect(
      revealStudentProblemMaterialWithOfflineCache(online, target, ownerId, revealRequest, false),
    ).rejects.toBeInstanceOf(ContentNetworkError)
    onlineReveal.mockRejectedValueOnce(new ContentNetworkError({ cause: new Error('offline') }))
    await expect(
      revealStudentProblemMaterialWithOfflineCache(online, target, ownerId, revealRequest, true),
    ).resolves.toEqual(reveal)
  })
})
