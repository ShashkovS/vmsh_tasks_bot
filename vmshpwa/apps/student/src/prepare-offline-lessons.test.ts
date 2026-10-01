/* eslint-disable @typescript-eslint/require-await -- Async in-memory transport/Cache Storage doubles model promise rejection and browser API signatures. */
import 'fake-indexeddb/auto'
import { afterEach, expect, it, vi } from 'vitest'
import {
  authContextSchema,
  studentHomeResponseSchema,
  studentCourseAccessResponseSchema,
  studentLessonListResponseSchema,
  studentProblemListResponseSchema,
  publishedContentSchema,
  runtimeConfigSchema,
  webContentDocumentSchema,
} from '@vmsh/contracts'
import homeFixture from '@vmsh/contracts/fixtures/courses/student-home.v1.json'
import problemsFixture from '@vmsh/contracts/fixtures/courses/student-problems.v1.json'
import webFixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import authFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { createStudentCourseClient } from '@vmsh/app-shell'
import type { createContentApiClient } from '@vmsh/content'
import {
  VmshOfflineDatabase,
  createOfflineAuthenticationStore,
  readLessonBundle,
  pruneOfflineDocuments,
  verifyLessonBundle,
  writeOfflineDocument,
} from '@vmsh/offline'
import { prepareOfflineLessons } from './prepare-offline-lessons'
import {
  createOfflineStudentCourseClient,
  createOfflineStudentPublishedContentClient,
} from './offline-student-data'

const databases: VmshOfflineDatabase[] = []
afterEach(async () => {
  vi.unstubAllGlobals()
  for (const db of databases) await db.delete()
  databases.length = 0
})

async function setup() {
  const database = new VmshOfflineDatabase({
    audience: 'student',
    instance: `bundle-${crypto.randomUUID()}`,
  })
  databases.push(database)
  const auth = authContextSchema.parse(authFixture.authContext)
  await createOfflineAuthenticationStore(database, 'student').save(auth)
  const home = studentHomeResponseSchema.parse(homeFixture.response)
  const enrollment = home.courses[0]!.enrollment
  const access = studentCourseAccessResponseSchema.parse({
    studentId: home.studentId,
    enrollments: [enrollment],
  })
  const lessons = enrollment.allowedGroups.map((group, index) => ({
    ...home.courses[0]!.currentLesson!,
    groupId: group.groupId,
    groupLessonId: `lesson-level-${index}`,
  }))
  const runtime = runtimeConfigSchema.parse(runtimeFixture.response)
  const document = webContentDocumentSchema.parse(webFixture.document)
  let revision = document.revisionId
  for (const lesson of lessons)
    lesson.materials.condition = {
      status: 'published',
      revisionId: revision,
      publishedAt: home.generatedAt,
      publicationVersion: 1,
    }
  const courseClient = {
    ...createStudentCourseClient(runtime),
    runtime,
    home: vi.fn(async () => home),
    list: vi.fn(async () => access),
    enrollment: vi.fn(async () => enrollment),
    updateEnrollment: vi.fn(async () => enrollment),
    progress: vi.fn(),
    offlineLessons: vi.fn(async () => ({ generatedAt: home.generatedAt, lessons })),
    lessons: vi.fn(async (_courseId, options) =>
      studentLessonListResponseSchema.parse({
        courseId: enrollment.course.courseId,
        groupId: options.groupId,
        activeGroupId: enrollment.activeGroupId,
        lessons: lessons.filter((lesson) => lesson.groupId === options.groupId),
        nextCursor: null,
      }),
    ),
    lesson: vi.fn(async (_courseId, lessonId) =>
      lessons.find((lesson) => lesson.groupLessonId === lessonId)!,
    ),
    problems: vi.fn(async (_courseId, lessonId) =>
      studentProblemListResponseSchema.parse({
        ...problemsFixture.response,
        groupLessonId: lessonId,
        conditionRevisionId: revision,
      }),
    ),
  } satisfies ReturnType<typeof createStudentCourseClient>
  const contentClient = {
    published: vi.fn(async (input) =>
      publishedContentSchema.parse({
        groupLessonId: input.groupLessonId,
        courseId: enrollment.course.courseId,
        groupId: lessons.find((lesson) => lesson.groupLessonId === input.groupLessonId)!.groupId,
        kind: 'condition',
        publicationId: 'publication-copy',
        publicationVersion: 1,
        publishedAt: home.generatedAt,
        revisionId: revision,
        document: { ...document, revisionId: revision },
      }),
    ),
  } satisfies Pick<ReturnType<typeof createContentApiClient>, 'published'>
  const stores = new Map<string, Map<string, Response>>()
  vi.stubGlobal('caches', {
    keys: async () => [...stores.keys()],
    delete: async (name: string) => stores.delete(name),
    open: async (name: string) => {
      if (!stores.has(name)) stores.set(name, new Map())
      const cache = stores.get(name)!
      return {
        keys: async () => [...cache.keys()].map((url) => new Request(url)),
        delete: async (request: Request) => cache.delete(request.url),
        match: async (url: string) => cache.get(url)?.clone(),
        put: async (url: string, response: Response) => {
          cache.set(url, response.clone())
        },
      }
    },
  })
  const fetchAsset = vi.fn<typeof fetch>(
    async () => new Response('<svg/>', { headers: { 'Content-Type': 'image/svg+xml' } }),
  )
  const controller = new AbortController()
  const options = {
    database,
    ownerId: auth.principal.accountId,
    runtime,
    signal: controller.signal,
    courseClient,
    contentClient,
    fetchAsset,
  }
  return {
    options,
    lessons,
    stores,
    controller,
    setRevision: (next: string) => {
      revision = next
      for (const lesson of lessons)
        if (lesson.materials.condition.status === 'published')
          lesson.materials.condition.revisionId = next
    },
  }
}

it('prepares every allowed level without visiting tasks and reads it when actually offline', async () => {
  const { options, lessons } = await setup()
  const bundle = await prepareOfflineLessons(options)
  expect(options.courseClient.updateEnrollment).not.toHaveBeenCalled()
  expect(options.contentClient.published).toHaveBeenCalledTimes(2)
  expect(await verifyLessonBundle(bundle)).toBe(true)
  await pruneOfflineDocuments(options.database, options.ownerId, { maxEntries: 1 })
  vi.stubGlobal('navigator', { onLine: false })
  const client = createOfflineStudentCourseClient(
    options.courseClient,
    options.database,
    options.ownerId,
  )
  const content = createOfflineStudentPublishedContentClient(
    { ...options.contentClient, audience: 'student' },
    options.database,
    options.ownerId,
  )
  options.courseClient.list.mockClear()
  options.contentClient.published.mockClear()
  expect((await client.list()).enrollments).toHaveLength(1)
  for (const lesson of lessons) {
    expect((await client.problems(lesson.courseId, lesson.groupLessonId)).groupLessonId).toBe(
      lesson.groupLessonId,
    )
    expect(
      (await content.published({ groupLessonId: lesson.groupLessonId, kind: 'condition' }))
        .revisionId,
    ).toBeTruthy()
  }
  expect(options.courseClient.list).not.toHaveBeenCalled()
  expect(options.contentClient.published).not.toHaveBeenCalled()
})

it('retains the complete previous copy when a later level fails, then replaces it on retry', async () => {
  const { options, setRevision } = await setup()
  const first = await prepareOfflineLessons(options)
  options.contentClient.published.mockRejectedValueOnce(new TypeError('interrupted'))
  await expect(prepareOfflineLessons(options)).rejects.toThrow('interrupted')
  expect(await readLessonBundle(options.database, options.ownerId)).toEqual(first)
  setRevision('revision-fixed-condition')
  const next = await prepareOfflineLessons(options)
  expect(
    next.documents
      .filter((entry) => entry.kind === 'published-content')
      .every((entry) => entry.version === 'revision-fixed-condition'),
  ).toBe(true)
  expect(await readLessonBundle(options.database, options.ownerId)).toEqual(next)
})

it('never commits after logout or cancellation', async () => {
  const { options, controller } = await setup()
  await createOfflineAuthenticationStore(options.database, 'student').clear()
  await expect(prepareOfflineLessons(options)).rejects.toThrow('Offline account changed')
  expect(await readLessonBundle(options.database, options.ownerId)).toBeNull()
  controller.abort()
  await expect(prepareOfflineLessons(options)).rejects.toThrow()
})

it('does not claim readiness when an image is missing from Cache Storage', async () => {
  const { options, stores } = await setup()
  const bundle = await prepareOfflineLessons(options)
  // The fixture includes figures that need fetching even though they were never rendered.
  expect(bundle.assets.length).toBeGreaterThan(0)
  stores.get(bundle.assetCacheName)!.clear()
  expect(await verifyLessonBundle(bundle)).toBe(false)
})

it('retains the previous copy when Cache Storage refuses the replacement', async () => {
  const { options } = await setup()
  const first = await prepareOfflineLessons(options)
  const open = caches.open.bind(caches)
  vi.spyOn(caches, 'open').mockImplementation(async (name) => {
    const cache = await open(name)
    if (name !== first.assetCacheName)
      cache.put = async () => {
        throw new DOMException('Full', 'QuotaExceededError')
      }
    return cache
  })
  await expect(prepareOfflineLessons(options)).rejects.toThrow('Full')
  expect(await readLessonBundle(options.database, options.ownerId)).toEqual(first)
})

it('resumes downloaded images when the connection fails before the final manifest check', async () => {
  const { options } = await setup()
  const listLessons = options.courseClient.offlineLessons.getMockImplementation()!
  options.courseClient.offlineLessons
    .mockImplementationOnce(listLessons)
    .mockRejectedValueOnce(new TypeError('disconnected'))
  await expect(prepareOfflineLessons(options)).rejects.toThrow('disconnected')
  expect(await readLessonBundle(options.database, options.ownerId)).toBeNull()
  const firstUrl = options.fetchAsset.mock.calls[0]![0]
  await prepareOfflineLessons(options)
  expect(options.fetchAsset.mock.calls.filter(([url]) => url === firstUrl)).toHaveLength(1)
})

it.each([-1_000, 1_000])(
  'keeps known Off hidden against an old bundle even with cache time offset %i',
  async (offset) => {
    const { options, lessons } = await setup()
    const bundle = await prepareOfflineLessons(options)
    const lesson = lessons[0]!
    for (const kind of ['student-problem-list', 'published-content'] as const) {
      const entry = bundle.documents.find((item) => item.kind === kind)!
      const parser = {
        parse: (payload: unknown) =>
          kind === 'published-content'
            ? publishedContentSchema.parse(payload)
            : studentProblemListResponseSchema.parse(payload),
      }
      const payload =
        kind === 'published-content'
          ? {
              ...publishedContentSchema.parse(entry.payload),
              problemReleaseVersion: 2,
              document: { ...publishedContentSchema.parse(entry.payload).document, problems: [] },
            }
          : {
              ...studentProblemListResponseSchema.parse(entry.payload),
              problemReleaseVersion: 2,
              problems: [],
            }
      await writeOfflineDocument(
        options.database,
        entry,
        `${entry.version}:release:2`,
        parser.parse(payload),
        parser,
        {
          now: () => new Date(Date.parse(entry.fetchedAt) + offset),
        },
      )
    }
    vi.stubGlobal('navigator', { onLine: false })
    const client = createOfflineStudentCourseClient(
      options.courseClient,
      options.database,
      options.ownerId,
    )
    const content = createOfflineStudentPublishedContentClient(
      { ...options.contentClient, audience: 'student' },
      options.database,
      options.ownerId,
    )
    expect((await client.problems(lesson.courseId, lesson.groupLessonId)).problems).toEqual([])
    expect(
      (await content.published({ groupLessonId: lesson.groupLessonId, kind: 'condition' })).document
        .problems,
    ).toEqual([])
  },
)
