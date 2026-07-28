// @vitest-environment node

import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it } from 'vitest'

import { VmshOfflineDatabase } from './database'
import {
  MAX_WRITTEN_SUBMISSION_PHOTOS,
  WrittenDraftStorageError,
  createWrittenSubmissionDraftStore,
  type WrittenDraftDescriptor,
} from './written-submission-draft'
import { type LocalDraftStorage } from './test-answer-draft'

const NOW = new Date('2026-07-28T13:00:00.000Z')
const PHOTO_ONE = '00000000-0000-4000-8000-000000000001'
const PHOTO_TWO = '00000000-0000-4000-8000-000000000002'

class MemoryStorage implements LocalDraftStorage {
  readonly values = new Map<string, string>()
  failNextWrite: Error | null = null

  get length() {
    return this.values.size
  }

  getItem(key: string) {
    return this.values.get(key) ?? null
  }

  key(index: number) {
    return [...this.values.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.values.delete(key)
  }

  setItem(key: string, value: string) {
    if (this.failNextWrite !== null) {
      const error = this.failNextWrite
      this.failNextWrite = null
      throw error
    }
    this.values.set(key, value)
  }
}

const databases = new Set<VmshOfflineDatabase>()

afterEach(async () => {
  await Promise.all(
    [...databases].map(async (database) => {
      database.close()
      await database.delete()
    }),
  )
  databases.clear()
})

function database(instance: string): VmshOfflineDatabase {
  const value = new VmshOfflineDatabase({ audience: 'student', instance })
  databases.add(value)
  return value
}

function descriptor(overrides: Partial<WrittenDraftDescriptor> = {}): WrittenDraftDescriptor {
  return {
    ownerId: 'account-student-one',
    problemId: 'problem-written-one',
    conditionRevisionId: 'condition-revision-one',
    configVersion: 3,
    ...overrides,
  }
}

function store(storage: MemoryStorage, target: VmshOfflineDatabase, instance: string) {
  let nextId = 10
  return createWrittenSubmissionDraftStore({ audience: 'student', instance }, storage, target, {
    now: () => NOW,
    randomUUID: () => `00000000-0000-4000-8000-${String(nextId++).padStart(12, '0')}`,
  })
}

async function blob(value: string, mediaType = 'image/webp'): Promise<Blob> {
  return new Response(value, { headers: { 'content-type': mediaType } }).blob()
}

describe('written-submission local draft store', () => {
  it('restores text, binary pages, order and resumable server IDs after reload', async () => {
    const storage = new MemoryStorage()
    const target = database('written-reload')
    const first = store(storage, target, 'written-reload')
    const draftDescriptor = descriptor()

    first.saveText(draftDescriptor, 'Решение с пояснением')
    await first.addPhoto(draftDescriptor, {
      id: PHOTO_ONE,
      fileName: 'page-1.webp',
      blob: await blob('first-page'),
      width: 1440,
      height: 1920,
      processing: 'client-webp',
    })
    await first.addPhoto(draftDescriptor, {
      id: PHOTO_TWO,
      fileName: 'page-2.webp',
      blob: await blob('second-page'),
      width: 1920,
      height: 1080,
      processing: 'client-webp',
    })
    first.reorderPhotos(draftDescriptor, [PHOTO_TWO, PHOTO_ONE])
    first.saveServerState(draftDescriptor, {
      threadId: 'thread-one',
      threadVersion: 2,
      entryId: 'entry-one',
      entryVersion: 4,
    })

    expect(
      (await target.writtenDraftPhotos.toArray()).map(({ id, blob }) => ({
        id,
        size: blob.size,
        type: blob.type,
      })),
    ).toEqual([
      { id: PHOTO_ONE, size: 10, type: 'image/webp' },
      { id: PHOTO_TWO, size: 11, type: 'image/webp' },
    ])

    const restored = await store(storage, target, 'written-reload').load(draftDescriptor)

    expect(restored.discardedPhotoIds).toEqual([])
    expect(restored.compatible).toMatchObject({
      text: 'Решение с пояснением',
      serverState: { threadId: 'thread-one', entryId: 'entry-one' },
      photos: [{ id: PHOTO_TWO }, { id: PHOTO_ONE }],
    })
    expect(await restored.compatible?.photos[0]?.blob.text()).toBe('second-page')
    expect(await restored.compatible?.photos[1]?.blob.text()).toBe('first-page')
  })

  it('keeps drafts isolated by owner, revision and runtime namespace', async () => {
    const storage = new MemoryStorage()
    const target = database('written-isolation')
    const agent = store(storage, target, 'written-isolation')
    agent.saveText(descriptor(), 'Текущий текст')

    expect((await agent.load(descriptor({ ownerId: 'account-student-two' }))).compatible).toBeNull()
    expect(
      await agent.load(
        descriptor({ conditionRevisionId: 'condition-revision-two', configVersion: 4 }),
      ),
    ).toMatchObject({
      compatible: null,
      incompatible: [{ text: 'Текущий текст', configVersion: 3 }],
    })

    const humanDatabase = database('human')
    expect((await store(storage, humanDatabase, 'human').load(descriptor())).compatible).toBeNull()
  })

  it('supports a temporary source blob only for server-side conversion fallback', async () => {
    const storage = new MemoryStorage()
    const target = database('written-fallback')
    const draftStore = store(storage, target, 'written-fallback')

    await draftStore.addPhoto(descriptor(), {
      id: PHOTO_ONE,
      fileName: 'iphone.heic',
      blob: await blob('heic-source', 'image/heic'),
      width: null,
      height: null,
      processing: 'server-fallback-source',
    })

    const restored = await draftStore.load(descriptor())
    expect(restored.compatible?.photos[0]).toMatchObject({
      mediaType: 'image/heic',
      processing: 'server-fallback-source',
      width: null,
      height: null,
    })
    expect(await restored.compatible?.photos[0]?.blob.text()).toBe('heic-source')
  })

  it('enforces ten unique pages and a complete deterministic order', async () => {
    const storage = new MemoryStorage()
    const target = database('written-limit')
    const draftStore = store(storage, target, 'written-limit')
    const ids: string[] = []
    for (let index = 0; index < MAX_WRITTEN_SUBMISSION_PHOTOS; index += 1) {
      const id = `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`
      ids.push(id)
      await draftStore.addPhoto(descriptor(), {
        id,
        fileName: `page-${index + 1}.webp`,
        blob: await blob(`page-${index + 1}`),
        width: 100,
        height: 100,
        processing: 'client-webp',
      })
    }

    await expect(
      draftStore.addPhoto(descriptor(), {
        fileName: 'page-11.webp',
        blob: await blob('page-11'),
        width: 100,
        height: 100,
        processing: 'client-webp',
      }),
    ).rejects.toThrow('at most 10')
    expect(() => draftStore.reorderPhotos(descriptor(), ids.slice(1))).toThrow('every current')
    expect(() => draftStore.reorderPhotos(descriptor(), [...ids.slice(0, 9), ids[0]!])).toThrow(
      'every current',
    )
    expect(
      draftStore.reorderPhotos(descriptor(), [...ids].reverse()).photos.map(({ id }) => id),
    ).toEqual([...ids].reverse())
  })

  it('compensates an IndexedDB blob when localStorage quota rejects its metadata', async () => {
    const storage = new MemoryStorage()
    const target = database('written-quota')
    const draftStore = store(storage, target, 'written-quota')
    draftStore.saveText(descriptor(), 'Этот текст уже сохранён')
    const quotaError = new DOMException('Storage full', 'QuotaExceededError')
    storage.failNextWrite = quotaError

    let thrown: unknown
    try {
      await draftStore.addPhoto(descriptor(), {
        id: PHOTO_ONE,
        fileName: 'page.webp',
        blob: await blob('page'),
        width: 100,
        height: 100,
        processing: 'client-webp',
      })
    } catch (error) {
      thrown = error
    }

    expect(thrown).toBeInstanceOf(WrittenDraftStorageError)
    expect(thrown).toMatchObject({ operation: 'write', cause: quotaError })
    expect(await target.writtenDraftPhotos.count()).toBe(0)
    expect((await draftStore.load(descriptor())).compatible?.text).toBe('Этот текст уже сохранён')
  })

  it('repairs missing/corrupt binary records and removes orphan blobs after reload', async () => {
    const storage = new MemoryStorage()
    const target = database('written-reconcile')
    const draftStore = store(storage, target, 'written-reconcile')
    await draftStore.addPhoto(descriptor(), {
      id: PHOTO_ONE,
      fileName: 'page-1.webp',
      blob: await blob('first'),
      width: 100,
      height: 100,
      processing: 'client-webp',
    })
    await draftStore.addPhoto(descriptor(), {
      id: PHOTO_TWO,
      fileName: 'page-2.webp',
      blob: await blob('second'),
      width: 100,
      height: 100,
      processing: 'client-webp',
    })
    await target.writtenDraftPhotos.delete(PHOTO_ONE)
    await target.writtenDraftPhotos.update(PHOTO_TWO, { byteSize: 999 })

    const restored = await draftStore.load(descriptor())

    expect(restored.compatible?.photos).toEqual([])
    expect(restored.discardedPhotoIds).toEqual([PHOTO_ONE, PHOTO_TWO])
    expect(await target.writtenDraftPhotos.count()).toBe(0)
    expect(JSON.parse(storage.getItem(draftStore.key(descriptor())) ?? '{}').photos).toEqual([])
  })

  it('persists sync state, removes one page metadata-first and clears one owner only', async () => {
    const storage = new MemoryStorage()
    const target = database('written-mutations')
    const draftStore = store(storage, target, 'written-mutations')
    const other = descriptor({ ownerId: 'account-student-two' })
    await draftStore.addPhoto(descriptor(), {
      id: PHOTO_ONE,
      fileName: 'page.webp',
      blob: await blob('first'),
      width: 100,
      height: 100,
      processing: 'client-webp',
    })
    await draftStore.addPhoto(other, {
      id: PHOTO_TWO,
      fileName: 'other.webp',
      blob: await blob('other'),
      width: 100,
      height: 100,
      processing: 'client-webp',
    })

    const uploaded = draftStore.updatePhoto(descriptor(), PHOTO_ONE, {
      syncState: 'uploaded',
      serverAttachmentId: 'attachment-one',
    })
    expect(uploaded.photos[0]).toMatchObject({
      syncState: 'uploaded',
      serverAttachmentId: 'attachment-one',
    })

    await draftStore.removePhoto(descriptor(), PHOTO_ONE)
    expect((await draftStore.load(descriptor())).compatible?.photos).toEqual([])
    expect(await target.writtenDraftPhotos.get(PHOTO_ONE)).toBeUndefined()

    await draftStore.clearOwner(other.ownerId)
    expect((await draftStore.load(other)).compatible).toBeNull()
    expect(await target.writtenDraftPhotos.get(PHOTO_TWO)).toBeUndefined()
  })

  it('rejects a mismatched database namespace before writing anything', () => {
    const storage = new MemoryStorage()
    const target = database('wrong-database')

    expect(() => store(storage, target, 'different-runtime')).toThrow('namespaces do not match')
    expect(storage.length).toBe(0)
  })
})
