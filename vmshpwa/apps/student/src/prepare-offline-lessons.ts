import { createStudentCourseClient, type StudentCourseClient } from '@vmsh/app-shell'
import { createContentApiClient } from '@vmsh/content'
import { type RuntimeConfig, type StudentOfflineLessonsResponse } from '@vmsh/contracts'
import {
  clearLessonAssetCaches,
  commitLessonBundle,
  lessonAssetCachePrefix,
  offlineDocumentEnvelopeSchema,
  readLessonBundle,
  type LessonBundle,
  type OfflineDocumentKind,
  type VmshOfflineDatabase,
} from '@vmsh/offline'

export interface PrepareOfflineLessonsOptions {
  database: VmshOfflineDatabase
  ownerId: string
  runtime: RuntimeConfig
  signal: AbortSignal
  courseClient?: StudentCourseClient & {
    offlineLessons(options: { signal: AbortSignal }): Promise<StudentOfflineLessonsResponse>
  }
  contentClient?: Pick<ReturnType<typeof createContentApiClient>, 'published'>
  fetchAsset?: typeof fetch
}

function figureUrls(value: unknown, urls = new Set<string>()): Set<string> {
  if (!value || typeof value !== 'object') return urls
  if (
    'status' in value &&
    value.status === 'available' &&
    'contentSha256' in value &&
    'src' in value &&
    typeof value.src === 'string'
  )
    urls.add(new URL(value.src, location.origin).href)
  for (const child of Object.values(value)) figureUrls(child, urls)
  return urls
}

/** Stage the full copy before replacing it; docs/offline-current-lessons.md. */
export async function prepareOfflineLessons(
  options: PrepareOfflineLessonsOptions,
): Promise<LessonBundle> {
  if (typeof navigator !== 'undefined' && navigator.locks) {
    return navigator.locks.request(
      `offline-lessons:${options.database.name}:${options.ownerId}`,
      { signal: options.signal },
      () => prepareLocked(options),
    )
  }
  return prepareLocked(options)
}

async function prepareLocked(options: PrepareOfflineLessonsOptions): Promise<LessonBundle> {
  const { database, ownerId, runtime, signal } = options
  const course = options.courseClient ?? createStudentCourseClient(runtime)
  const content = options.contentClient ?? createContentApiClient(runtime)
  const request = { signal }
  const savedAt = new Date().toISOString()
  const documents: LessonBundle['documents'] = []
  const add = (
    kind: OfflineDocumentKind,
    resourceParts: string[],
    payload: unknown,
    version = savedAt,
  ) => {
    documents.push(
      offlineDocumentEnvelopeSchema.parse({
        schemaVersion: 1,
        ownerId,
        kind,
        resourceParts,
        version,
        fetchedAt: savedAt,
        expiresAt: new Date(Date.now() + 86400_000).toISOString(),
        payload,
      }),
    )
  }
  const access = await course.list(request)
  add('student-course-access', ['current'], access)
  const home = await course.home(request)
  add('student-home', ['current'], home)
  const current = await course.offlineLessons(request)
  for (const enrollment of access.enrollments) {
    signal.throwIfAborted()
    add(
      'student-course-enrollment',
      [enrollment.course.courseId],
      enrollment,
      String(enrollment.version),
    )
    for (const group of enrollment.allowedGroups) {
      const archive = await course.lessons(enrollment.course.courseId, {
        ...request,
        groupId: group.groupId,
      })
      add('student-lesson-list', [enrollment.course.courseId, group.groupId, 'first-page'], archive)
      if (group.groupId === enrollment.activeGroupId)
        add(
          'student-lesson-list',
          [enrollment.course.courseId, 'active-group', 'first-page'],
          archive,
        )
    }
  }
  for (const lesson of current.lessons) {
    signal.throwIfAborted()
    if (
      !access.enrollments.some(
        (entry) =>
          entry.course.courseId === lesson.courseId &&
          entry.allowedGroups.some((group) => group.groupId === lesson.groupId),
      )
    )
      throw new Error('Unexpected lesson scope')
    add('student-lesson', [lesson.courseId, lesson.groupLessonId], lesson, String(lesson.version))
    if (lesson.materials.condition.status !== 'published') continue
    const problems = await course.problems(lesson.courseId, lesson.groupLessonId, request)
    const condition = await content.published(
      { groupLessonId: lesson.groupLessonId, kind: 'condition' },
      request,
    )
    if (
      problems.conditionRevisionId !== condition.revisionId ||
      lesson.materials.condition.revisionId !== condition.revisionId
    )
      throw new Error('Publication changed during offline preparation')
    add(
      'student-problem-list',
      [lesson.courseId, lesson.groupLessonId],
      problems,
      problems.conditionRevisionId,
    )
    // Same-source figure publications have distinct identities; docs/figure-layout.md.
    add(
      'published-content',
      [lesson.groupLessonId, 'condition'],
      condition,
      `${condition.revisionId}:${condition.publicationId}`,
    )
  }
  const previous = await readLessonBundle(database, ownerId)
  const prefix = lessonAssetCachePrefix(database.name, ownerId)
  // Reuse an interrupted staging cache, never the previous complete copy.
  const assetCacheName =
    (await caches.keys()).find(
      (name) => name.startsWith(prefix) && name !== previous?.assetCacheName,
    ) ?? `${prefix}${crypto.randomUUID()}`
  const assets = [...figureUrls(documents)]
  const bundle = { savedAt, assetCacheName, assets, documents }
  const cache = await caches.open(assetCacheName)
  const oldCache = previous ? await caches.open(previous.assetCacheName) : null
  let assetBytes = 0
  try {
    for (const request of await cache.keys()) {
      if (!assets.includes(request.url)) await cache.delete(request)
    }
    for (const url of assets) {
      signal.throwIfAborted()
      const response =
        (await cache.match(url)) ??
        (await oldCache?.match(url)) ??
        (await (options.fetchAsset ?? fetch)(url, { signal }))
      if (!response.ok || !response.headers.get('content-type')?.startsWith('image/'))
        throw new Error('Offline image unavailable')
      assetBytes += (await response.clone().arrayBuffer()).byteLength
      if (assetBytes > 15 * 1024 * 1024) throw new Error('Offline image budget exceeded')
      await cache.put(url, response)
    }
    signal.throwIfAborted()
    const latest = await course.offlineLessons(request)
    if (JSON.stringify(latest.lessons) !== JSON.stringify(current.lessons))
      throw new Error('Lessons changed during offline preparation')
    await commitLessonBundle(database, ownerId, bundle, signal)
    await clearLessonAssetCaches(database.name, ownerId, assetCacheName)
    return bundle
  } finally {
    // Interrupted images can resume, but must not outlive their owning identity.
    if ((await database.authentication.get('current'))?.ownerId !== ownerId)
      await caches.delete(assetCacheName)
  }
}
