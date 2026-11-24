import { z } from 'zod'
import {
  studentHomeResponseSchema,
  studentCourseAccessResponseSchema,
  courseEnrollmentSchema,
  studentLessonListResponseSchema,
  studentLessonSummarySchema,
  studentProblemListResponseSchema,
  publishedContentSchema,
} from '@vmsh/contracts'
import type { VmshOfflineDatabase } from './database'
import {
  offlineDocumentEnvelopeSchema,
  writeOfflineDocument,
  readOfflineDocument,
  DEFAULT_OFFLINE_DOCUMENT_MAX_BYTES,
} from './document-cache'

const documentParsers = {
  'student-home': studentHomeResponseSchema,
  'student-course-access': studentCourseAccessResponseSchema,
  'student-course-enrollment': courseEnrollmentSchema,
  'student-lesson-list': studentLessonListResponseSchema,
  'student-lesson': studentLessonSummarySchema,
  'student-problem-list': studentProblemListResponseSchema,
  'published-content': publishedContentSchema,
}
const bundleDocumentSchema = offlineDocumentEnvelopeSchema.superRefine((entry, context) => {
  const parser = documentParsers[entry.kind as keyof typeof documentParsers]
  if (!parser || !parser.safeParse(entry.payload).success)
    context.addIssue({ code: 'custom', message: 'Invalid offline bundle document' })
})

/** Atomic, owner-scoped complete copy; see docs/offline-current-lessons.md. */
export const lessonBundleSchema = z
  .object({
    savedAt: z.iso.datetime(),
    assetCacheName: z.string(),
    assets: z.array(z.string().url()),
    documents: z.array(bundleDocumentSchema).min(2),
  })
  .strict()
export type LessonBundle = z.infer<typeof lessonBundleSchema>
export const lessonBundleDescriptor = (ownerId: string) => ({
  ownerId,
  kind: 'student-offline-bundle' as const,
  resourceParts: ['current'],
})
export const lessonAssetCachePrefix = (databaseName: string, ownerId: string) =>
  `vmsh-student-offline-assets-${encodeURIComponent(JSON.stringify([databaseName, ownerId]))}-`

export async function readLessonBundle(database: VmshOfflineDatabase, ownerId: string) {
  const copy = await readOfflineDocument(
    database,
    lessonBundleDescriptor(ownerId),
    lessonBundleSchema,
  )
  if (
    !copy ||
    !copy.data.assetCacheName.startsWith(lessonAssetCachePrefix(database.name, ownerId)) ||
    copy.data.documents.some((document) => document.ownerId !== ownerId)
  )
    return null
  return copy.data
}

export async function verifyLessonBundle(bundle: LessonBundle): Promise<boolean> {
  if (!bundle.assets.length) return true
  if (typeof caches === 'undefined') return false
  const cache = await caches.open(bundle.assetCacheName)
  for (const url of bundle.assets) if (!(await cache.match(url))) return false
  return true
}

export async function commitLessonBundle(
  database: VmshOfflineDatabase,
  ownerId: string,
  bundle: LessonBundle,
  signal: AbortSignal,
): Promise<void> {
  const parsed = lessonBundleSchema.parse(bundle)
  if (parsed.documents.some((document) => document.ownerId !== ownerId))
    throw new Error('Wrong bundle owner')
  // Reserve headroom for its envelope. Never evict the previous complete copy to fit a new one.
  if (
    new TextEncoder().encode(JSON.stringify(parsed)).byteLength >
    DEFAULT_OFFLINE_DOCUMENT_MAX_BYTES - 4096
  )
    throw new Error('Offline lesson document budget exceeded')
  await database.transaction('rw', database.authentication, database.documents, async () => {
    signal.throwIfAborted()
    const identity = await database.authentication.get('current')
    if (identity?.ownerId !== ownerId) throw new Error('Offline account changed')
    await writeOfflineDocument(
      database,
      lessonBundleDescriptor(ownerId),
      parsed.savedAt,
      parsed,
      lessonBundleSchema,
    )
    signal.throwIfAborted()
  })
}

/** Individual transport fallbacks can find navigation/conditions in the complete copy. */
export async function bundledDocument(
  database: VmshOfflineDatabase,
  descriptor: {
    ownerId: string
    kind: string
    resourceParts: readonly string[]
  },
) {
  const bundle = await readLessonBundle(database, descriptor.ownerId)
  return (
    bundle?.documents.find(
      (document) =>
        document.kind === descriptor.kind &&
        JSON.stringify(document.resourceParts) === JSON.stringify(descriptor.resourceParts),
    ) ?? null
  )
}

export async function clearLessonAssetCaches(databaseName: string, ownerId: string, keep?: string) {
  if (typeof caches === 'undefined') return
  const prefix = lessonAssetCachePrefix(databaseName, ownerId)
  await Promise.all(
    (await caches.keys())
      .filter((name) => name.startsWith(prefix) && name !== keep)
      .map((name) => caches.delete(name)),
  )
}
