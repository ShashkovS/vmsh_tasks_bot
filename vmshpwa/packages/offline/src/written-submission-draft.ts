import { z } from 'zod'

import {
  browserStorageNamespaceSchema,
  createBrowserStorageNamespace,
  publicIdSchema,
  runtimeInstanceSchema,
  type BrowserStorageNamespace,
} from '@vmsh/contracts'

import {
  offlineAudienceSchema,
  type OfflineAudience,
  type VmshOfflineDatabase,
  type WrittenDraftPhotoRecord,
} from './database'
import { type LocalDraftStorage } from './test-answer-draft'

/**
 * Durable browser draft for Phase 5. Text, ordering and resumable server IDs
 * are written to localStorage; binary pages are owner-scoped in Dexie. The
 * split follows `dev/development-plan/09-phase-5-written-submissions.md`.
 */

export const WRITTEN_SUBMISSION_DRAFT_VERSION = 1 as const
export const MAX_WRITTEN_SUBMISSION_PHOTOS = 10
export const MAX_WRITTEN_DRAFT_PHOTO_BYTES = 25 * 1024 * 1024

const writtenDraftRuntimeSchema = z
  .object({
    audience: offlineAudienceSchema,
    instance: runtimeInstanceSchema,
  })
  .strict()

export type WrittenDraftRuntime = z.infer<typeof writtenDraftRuntimeSchema>

export const writtenDraftDescriptorSchema = z
  .object({
    ownerId: publicIdSchema,
    problemId: publicIdSchema,
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
  })
  .strict()
export type WrittenDraftDescriptor = z.infer<typeof writtenDraftDescriptorSchema>

export const writtenDraftServerStateSchema = z
  .object({
    threadId: publicIdSchema,
    threadVersion: z.number().int().positive(),
    entryId: publicIdSchema,
    entryVersion: z.number().int().positive(),
  })
  .strict()
export type WrittenDraftServerState = z.infer<typeof writtenDraftServerStateSchema>

export const writtenDraftPhotoProcessingSchema = z.enum(['client-webp', 'server-fallback-source'])
export type WrittenDraftPhotoProcessing = z.infer<typeof writtenDraftPhotoProcessingSchema>

export const writtenDraftPhotoSyncStateSchema = z.enum([
  'local',
  'queued',
  'uploading',
  'uploaded',
  'failed',
])
export type WrittenDraftPhotoSyncState = z.infer<typeof writtenDraftPhotoSyncStateSchema>

export const writtenDraftPhotoSchema = z
  .object({
    id: z.uuid(),
    fileName: z.string().trim().min(1).max(255),
    mediaType: z.string().trim().min(1).max(100),
    byteSize: z.number().int().positive().max(MAX_WRITTEN_DRAFT_PHOTO_BYTES),
    width: z.number().int().positive().max(100_000).nullable(),
    height: z.number().int().positive().max(100_000).nullable(),
    processing: writtenDraftPhotoProcessingSchema,
    syncState: writtenDraftPhotoSyncStateSchema,
    serverAttachmentId: publicIdSchema.nullable(),
    createdAt: z.iso.datetime(),
    updatedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((photo, context) => {
    if (photo.processing === 'client-webp') {
      if (photo.mediaType !== 'image/webp') {
        context.addIssue({
          code: 'custom',
          message: 'A client-compressed photo must be WebP',
          path: ['mediaType'],
        })
      }
      if (
        photo.width === null ||
        photo.height === null ||
        photo.width > 1920 ||
        photo.height > 1920
      ) {
        context.addIssue({
          code: 'custom',
          message: 'A client-compressed photo must expose dimensions no larger than 1920',
          path: ['width'],
        })
      }
    }
    if ((photo.syncState === 'uploaded') !== (photo.serverAttachmentId !== null)) {
      context.addIssue({
        code: 'custom',
        message: 'Only an uploaded photo may reference a server attachment',
        path: ['serverAttachmentId'],
      })
    }
  })
export type WrittenDraftPhoto = z.infer<typeof writtenDraftPhotoSchema>

export const writtenSubmissionDraftSchema = z
  .object({
    schemaVersion: z.literal(WRITTEN_SUBMISSION_DRAFT_VERSION),
    namespace: browserStorageNamespaceSchema,
    audience: z.literal('student'),
    ownerId: publicIdSchema,
    problemId: publicIdSchema,
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
    text: z.string().max(16_384),
    photos: z.array(writtenDraftPhotoSchema).max(MAX_WRITTEN_SUBMISSION_PHOTOS),
    serverState: writtenDraftServerStateSchema.nullable(),
    updatedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((draft, context) => {
    const [, , namespaceAudience] = draft.namespace.split(':')
    if (namespaceAudience !== draft.audience) {
      context.addIssue({
        code: 'custom',
        message: 'Draft audience must match its browser namespace',
        path: ['audience'],
      })
    }
    const photoIds = draft.photos.map((photo) => photo.id)
    if (new Set(photoIds).size !== photoIds.length) {
      context.addIssue({
        code: 'custom',
        message: 'Draft photo IDs must be unique',
        path: ['photos'],
      })
    }
  })
export type WrittenSubmissionDraft = z.infer<typeof writtenSubmissionDraftSchema>

export interface ResolvedWrittenDraftPhoto extends WrittenDraftPhoto {
  blob: Blob
}

export interface ResolvedWrittenSubmissionDraft extends Omit<WrittenSubmissionDraft, 'photos'> {
  photos: ResolvedWrittenDraftPhoto[]
}

export interface WrittenSubmissionDraftLoadResult {
  compatible: ResolvedWrittenSubmissionDraft | null
  incompatible: WrittenSubmissionDraft[]
  discardedPhotoIds: string[]
}

export interface AddWrittenDraftPhotoInput {
  id?: string
  fileName: string
  blob: Blob
  width: number | null
  height: number | null
  processing: WrittenDraftPhotoProcessing
}

export interface UpdateWrittenDraftPhotoInput {
  syncState: WrittenDraftPhotoSyncState
  serverAttachmentId?: string | null
}

export type WrittenDraftStorageOperation = 'enumerate' | 'read' | 'write' | 'remove'

export class WrittenDraftStorageError extends Error {
  readonly operation: WrittenDraftStorageOperation

  constructor(operation: WrittenDraftStorageOperation, cause: unknown) {
    super(`Written-submission draft storage failed during ${operation}`, { cause })
    this.name = 'WrittenDraftStorageError'
    this.operation = operation
  }
}

export interface WrittenSubmissionDraftStoreOptions {
  now?: () => Date
  randomUUID?: () => string
}

export interface WrittenSubmissionDraftStore {
  readonly audience: OfflineAudience
  readonly namespace: BrowserStorageNamespace
  key(descriptor: WrittenDraftDescriptor): string
  load(descriptor: WrittenDraftDescriptor): Promise<WrittenSubmissionDraftLoadResult>
  saveText(descriptor: WrittenDraftDescriptor, text: string): WrittenSubmissionDraft
  saveServerState(
    descriptor: WrittenDraftDescriptor,
    serverState: WrittenDraftServerState | null,
  ): WrittenSubmissionDraft
  addPhoto(
    descriptor: WrittenDraftDescriptor,
    input: AddWrittenDraftPhotoInput,
  ): Promise<WrittenSubmissionDraft>
  reorderPhotos(
    descriptor: WrittenDraftDescriptor,
    orderedPhotoIds: string[],
  ): WrittenSubmissionDraft
  updatePhoto(
    descriptor: WrittenDraftDescriptor,
    photoId: string,
    input: UpdateWrittenDraftPhotoInput,
  ): WrittenSubmissionDraft
  removePhoto(descriptor: WrittenDraftDescriptor, photoId: string): Promise<WrittenSubmissionDraft>
  clear(descriptor: WrittenDraftDescriptor): Promise<void>
  clearOwner(ownerId: string): Promise<void>
}

const DRAFT_KEY_MARKER = ':draft:written-submission:'

function storagePrefix(namespace: BrowserStorageNamespace): string {
  return `${namespace}${DRAFT_KEY_MARKER}`
}

function descriptor(value: WrittenDraftDescriptor): WrittenDraftDescriptor {
  return writtenDraftDescriptorSchema.parse(value)
}

function draftKey(namespace: BrowserStorageNamespace, value: WrittenDraftDescriptor): string {
  const parsed = descriptor(value)
  return `${storagePrefix(namespace)}${JSON.stringify([
    parsed.ownerId,
    parsed.problemId,
    parsed.conditionRevisionId,
    parsed.configVersion,
  ])}`
}

function draftDescriptor(draft: WrittenSubmissionDraft): WrittenDraftDescriptor {
  return {
    ownerId: draft.ownerId,
    problemId: draft.problemId,
    conditionRevisionId: draft.conditionRevisionId,
    configVersion: draft.configVersion,
  }
}

function enumerateKeys(storage: LocalDraftStorage, prefix: string): string[] {
  try {
    const keys: string[] = []
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key?.startsWith(prefix)) keys.push(key)
    }
    return keys
  } catch (error) {
    throw new WrittenDraftStorageError('enumerate', error)
  }
}

function readRaw(storage: LocalDraftStorage, key: string): string | null {
  try {
    return storage.getItem(key)
  } catch (error) {
    throw new WrittenDraftStorageError('read', error)
  }
}

function writeDraft(
  storage: LocalDraftStorage,
  key: string,
  draft: WrittenSubmissionDraft,
): WrittenSubmissionDraft {
  const parsed = writtenSubmissionDraftSchema.parse(draft)
  try {
    storage.setItem(key, JSON.stringify(parsed))
  } catch (error) {
    throw new WrittenDraftStorageError('write', error)
  }
  return parsed
}

function removeRaw(storage: LocalDraftStorage, key: string): void {
  try {
    storage.removeItem(key)
  } catch (error) {
    throw new WrittenDraftStorageError('remove', error)
  }
}

function parseStoredDraft(
  storage: LocalDraftStorage,
  key: string,
  namespace: BrowserStorageNamespace,
): WrittenSubmissionDraft | null {
  const raw = readRaw(storage, key)
  if (raw === null) return null
  let payload: unknown
  try {
    payload = JSON.parse(raw)
  } catch {
    removeRaw(storage, key)
    return null
  }
  const parsed = writtenSubmissionDraftSchema.safeParse(payload)
  if (
    !parsed.success ||
    parsed.data.namespace !== namespace ||
    draftKey(namespace, draftDescriptor(parsed.data)) !== key
  ) {
    removeRaw(storage, key)
    return null
  }
  return parsed.data
}

function emptyDraft(
  namespace: BrowserStorageNamespace,
  value: WrittenDraftDescriptor,
  now: Date,
): WrittenSubmissionDraft {
  return writtenSubmissionDraftSchema.parse({
    schemaVersion: WRITTEN_SUBMISSION_DRAFT_VERSION,
    namespace,
    audience: 'student',
    ...descriptor(value),
    text: '',
    photos: [],
    serverState: null,
    updatedAt: now.toISOString(),
  })
}

function photoRecordMatchesMetadata(
  record: WrittenDraftPhotoRecord,
  photo: WrittenDraftPhoto,
  expected: WrittenDraftDescriptor,
  expectedDraftKey: string,
): boolean {
  const blob = record.blob as unknown
  const isBlobLike =
    typeof blob === 'object' &&
    blob !== null &&
    typeof (blob as Blob).size === 'number' &&
    typeof (blob as Blob).type === 'string' &&
    typeof (blob as Blob).arrayBuffer === 'function'
  return (
    record.id === photo.id &&
    record.draftKey === expectedDraftKey &&
    record.ownerId === expected.ownerId &&
    record.problemId === expected.problemId &&
    record.conditionRevisionId === expected.conditionRevisionId &&
    record.configVersion === expected.configVersion &&
    record.fileName === photo.fileName &&
    record.mediaType === photo.mediaType &&
    record.byteSize === photo.byteSize &&
    record.width === photo.width &&
    record.height === photo.height &&
    record.processing === photo.processing &&
    record.createdAt === photo.createdAt &&
    isBlobLike &&
    record.blob.size === photo.byteSize &&
    record.blob.type === photo.mediaType
  )
}

function withTimestamp(
  draft: WrittenSubmissionDraft,
  now: Date,
  changes: Partial<Pick<WrittenSubmissionDraft, 'text' | 'photos' | 'serverState'>>,
): WrittenSubmissionDraft {
  return writtenSubmissionDraftSchema.parse({
    ...draft,
    ...changes,
    updatedAt: now.toISOString(),
  })
}

export function createWrittenSubmissionDraftStore(
  runtime: WrittenDraftRuntime,
  storage: LocalDraftStorage,
  database: VmshOfflineDatabase,
  options: WrittenSubmissionDraftStoreOptions = {},
): WrittenSubmissionDraftStore {
  const parsedRuntime = writtenDraftRuntimeSchema.parse(runtime)
  if (parsedRuntime.audience !== 'student') {
    throw new TypeError('Written-submission drafts belong only to the Student audience')
  }
  if (database.name !== createBrowserStorageNamespace(parsedRuntime)) {
    throw new TypeError('Written-submission draft storage namespaces do not match')
  }
  const namespace = createBrowserStorageNamespace(parsedRuntime)
  const prefix = storagePrefix(namespace)
  const now = options.now ?? (() => new Date())
  const randomUUID = options.randomUUID ?? (() => globalThis.crypto.randomUUID())

  function current(value: WrittenDraftDescriptor): WrittenSubmissionDraft {
    const parsedDescriptor = descriptor(value)
    const key = draftKey(namespace, parsedDescriptor)
    return (
      parseStoredDraft(storage, key, namespace) ?? emptyDraft(namespace, parsedDescriptor, now())
    )
  }

  function save(
    value: WrittenDraftDescriptor,
    draft: WrittenSubmissionDraft,
  ): WrittenSubmissionDraft {
    return writeDraft(storage, draftKey(namespace, value), draft)
  }

  return {
    audience: parsedRuntime.audience,
    namespace,

    key(value) {
      return draftKey(namespace, value)
    },

    async load(value) {
      const parsedDescriptor = descriptor(value)
      const key = draftKey(namespace, parsedDescriptor)
      const parsedDraft = parseStoredDraft(storage, key, namespace)
      const incompatible: WrittenSubmissionDraft[] = []
      for (const candidateKey of enumerateKeys(storage, prefix)) {
        if (candidateKey === key) continue
        const candidate = parseStoredDraft(storage, candidateKey, namespace)
        if (
          candidate?.ownerId === parsedDescriptor.ownerId &&
          candidate.problemId === parsedDescriptor.problemId
        ) {
          incompatible.push(candidate)
        }
      }
      incompatible.sort(
        (left, right) =>
          right.updatedAt.localeCompare(left.updatedAt) ||
          right.conditionRevisionId.localeCompare(left.conditionRevisionId) ||
          right.configVersion - left.configVersion,
      )

      const storedRecords = await database.writtenDraftPhotos
        .where('draftKey')
        .equals(key)
        .toArray()
      if (!parsedDraft) {
        const discardedPhotoIds = storedRecords.map((record) => record.id).sort()
        if (discardedPhotoIds.length > 0) {
          await database.writtenDraftPhotos.bulkDelete(discardedPhotoIds)
        }
        return { compatible: null, incompatible, discardedPhotoIds }
      }

      const records = new Map(storedRecords.map((record) => [record.id, record]))
      const photos: ResolvedWrittenDraftPhoto[] = []
      const discardedPhotoIds: string[] = []
      for (const metadata of parsedDraft.photos) {
        const record = records.get(metadata.id)
        if (!record || !photoRecordMatchesMetadata(record, metadata, parsedDescriptor, key)) {
          discardedPhotoIds.push(metadata.id)
          records.delete(metadata.id)
          continue
        }
        records.delete(metadata.id)
        photos.push({ ...metadata, blob: record.blob })
      }
      discardedPhotoIds.push(...records.keys())
      discardedPhotoIds.sort()

      let reconciled = parsedDraft
      if (photos.length !== parsedDraft.photos.length) {
        reconciled = save(
          parsedDescriptor,
          withTimestamp(parsedDraft, now(), {
            photos: photos.map(({ blob, ...metadata }) => {
              void blob
              return metadata
            }),
          }),
        )
      }
      if (discardedPhotoIds.length > 0) {
        await database.writtenDraftPhotos.bulkDelete(discardedPhotoIds)
      }
      return {
        compatible: { ...reconciled, photos },
        incompatible,
        discardedPhotoIds,
      }
    },

    saveText(value, text) {
      const parsedDescriptor = descriptor(value)
      return save(parsedDescriptor, withTimestamp(current(parsedDescriptor), now(), { text }))
    },

    saveServerState(value, serverState) {
      const parsedDescriptor = descriptor(value)
      const parsedServerState =
        serverState === null ? null : writtenDraftServerStateSchema.parse(serverState)
      return save(
        parsedDescriptor,
        withTimestamp(current(parsedDescriptor), now(), { serverState: parsedServerState }),
      )
    },

    async addPhoto(value, input) {
      const parsedDescriptor = descriptor(value)
      const key = draftKey(namespace, parsedDescriptor)
      const existing = current(parsedDescriptor)
      if (existing.photos.length >= MAX_WRITTEN_SUBMISSION_PHOTOS) {
        throw new RangeError(
          `A written submission accepts at most ${MAX_WRITTEN_SUBMISSION_PHOTOS} photos`,
        )
      }
      const timestamp = now().toISOString()
      const id = z.uuid().parse(input.id ?? randomUUID())
      const mediaType = input.blob.type || 'application/octet-stream'
      const metadata = writtenDraftPhotoSchema.parse({
        id,
        fileName: input.fileName,
        mediaType,
        byteSize: input.blob.size,
        width: input.width,
        height: input.height,
        processing: input.processing,
        syncState: 'local',
        serverAttachmentId: null,
        createdAt: timestamp,
        updatedAt: timestamp,
      })
      const record: WrittenDraftPhotoRecord = {
        ...metadata,
        draftKey: key,
        ownerId: parsedDescriptor.ownerId,
        problemId: parsedDescriptor.problemId,
        conditionRevisionId: parsedDescriptor.conditionRevisionId,
        configVersion: parsedDescriptor.configVersion,
        blob: input.blob,
      }
      await database.writtenDraftPhotos.add(record)
      try {
        const latest = current(parsedDescriptor)
        if (latest.photos.length >= MAX_WRITTEN_SUBMISSION_PHOTOS) {
          throw new RangeError(
            `A written submission accepts at most ${MAX_WRITTEN_SUBMISSION_PHOTOS} photos`,
          )
        }
        return save(
          parsedDescriptor,
          withTimestamp(latest, now(), { photos: [...latest.photos, metadata] }),
        )
      } catch (error) {
        await database.writtenDraftPhotos.delete(id)
        throw error
      }
    },

    reorderPhotos(value, orderedPhotoIds) {
      const parsedDescriptor = descriptor(value)
      const draft = current(parsedDescriptor)
      if (
        orderedPhotoIds.length !== draft.photos.length ||
        new Set(orderedPhotoIds).size !== orderedPhotoIds.length ||
        orderedPhotoIds.some((id) => !draft.photos.some((photo) => photo.id === id))
      ) {
        throw new TypeError('Photo order must contain every current photo exactly once')
      }
      const photosById = new Map(draft.photos.map((photo) => [photo.id, photo]))
      return save(
        parsedDescriptor,
        withTimestamp(draft, now(), {
          photos: orderedPhotoIds.map((id) => {
            const photo = photosById.get(id)
            if (!photo) throw new TypeError('Unknown photo in written draft order')
            return photo
          }),
        }),
      )
    },

    updatePhoto(value, photoId, input) {
      const parsedDescriptor = descriptor(value)
      const parsedPhotoId = z.uuid().parse(photoId)
      const draft = current(parsedDescriptor)
      if (!draft.photos.some((photo) => photo.id === parsedPhotoId)) {
        throw new TypeError('Unknown photo in written draft')
      }
      const timestamp = now().toISOString()
      return save(
        parsedDescriptor,
        withTimestamp(draft, now(), {
          photos: draft.photos.map((photo) =>
            photo.id === parsedPhotoId
              ? writtenDraftPhotoSchema.parse({
                  ...photo,
                  syncState: input.syncState,
                  serverAttachmentId: input.serverAttachmentId ?? null,
                  updatedAt: timestamp,
                })
              : photo,
          ),
        }),
      )
    },

    async removePhoto(value, photoId) {
      const parsedDescriptor = descriptor(value)
      const parsedPhotoId = z.uuid().parse(photoId)
      const draft = current(parsedDescriptor)
      if (!draft.photos.some((photo) => photo.id === parsedPhotoId)) return draft
      const updated = save(
        parsedDescriptor,
        withTimestamp(draft, now(), {
          photos: draft.photos.filter((photo) => photo.id !== parsedPhotoId),
        }),
      )
      await database.writtenDraftPhotos.delete(parsedPhotoId)
      return updated
    },

    async clear(value) {
      const parsedDescriptor = descriptor(value)
      const key = draftKey(namespace, parsedDescriptor)
      removeRaw(storage, key)
      await database.writtenDraftPhotos.where('draftKey').equals(key).delete()
    },

    async clearOwner(ownerId) {
      const parsedOwnerId = publicIdSchema.parse(ownerId)
      for (const key of enumerateKeys(storage, prefix)) {
        const draft = parseStoredDraft(storage, key, namespace)
        if (draft?.ownerId === parsedOwnerId) removeRaw(storage, key)
      }
      await database.writtenDraftPhotos.where('ownerId').equals(parsedOwnerId).delete()
    },
  }
}
