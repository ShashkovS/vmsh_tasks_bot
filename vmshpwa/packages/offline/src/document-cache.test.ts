import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it } from 'vitest'
import { z } from 'zod'

import {
  offlineDocumentKey,
  offlineDocumentUsage,
  pruneOfflineDocuments,
  readOfflineDocument,
  writeOfflineDocument,
} from './document-cache'
import { VmshOfflineDatabase } from './database'

const databases = new Set<VmshOfflineDatabase>()
const NOW = new Date('2026-07-28T10:00:00.000Z')
const payloadSchema = z.object({ title: z.string(), revision: z.number().int() }).strict()

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

function descriptor(ownerId = 'account-student-one', resource = 'lesson-one') {
  return {
    ownerId,
    kind: 'published-content' as const,
    resourceParts: [resource, 'condition'],
  }
}

describe('offline document cache', () => {
  it('round-trips only contract-valid owner-scoped JSON', async () => {
    const target = database('document-valid')
    await writeOfflineDocument(
      target,
      descriptor(),
      'revision-one',
      { title: 'Сохранённое условие', revision: 1 },
      payloadSchema,
      { now: () => NOW },
    )

    await expect(
      readOfflineDocument(target, descriptor(), payloadSchema, { now: () => NOW }),
    ).resolves.toMatchObject({
      data: { title: 'Сохранённое условие', revision: 1 },
      stale: false,
      version: 'revision-one',
    })
    await expect(
      writeOfflineDocument<unknown>(
        target,
        descriptor(),
        'revision-bad',
        { title: 'Нет revision' },
        payloadSchema,
      ),
    ).rejects.toThrow()
  })

  it('returns an expired last copy as stale instead of inventing fresh state', async () => {
    const target = database('document-stale')
    await writeOfflineDocument(
      target,
      descriptor(),
      'revision-one',
      { title: 'Последняя копия', revision: 1 },
      payloadSchema,
      { now: () => NOW, ttlMilliseconds: 1_000 },
    )

    const cached = await readOfflineDocument(target, descriptor(), payloadSchema, {
      now: () => new Date(NOW.getTime() + 1_001),
    })
    expect(cached?.stale).toBe(true)
    expect(await target.documents.count()).toBe(1)
  })

  it('does not cross owner or resource boundaries', async () => {
    const target = database('document-owner')
    await writeOfflineDocument(
      target,
      descriptor('account-student-one'),
      'revision-one',
      { title: 'Первый', revision: 1 },
      payloadSchema,
    )

    await expect(
      readOfflineDocument(target, descriptor('account-student-two'), payloadSchema),
    ).resolves.toBeNull()
    await expect(
      readOfflineDocument(target, descriptor('account-student-one', 'lesson-two'), payloadSchema),
    ).resolves.toBeNull()
  })

  it('removes a corrupted envelope before protected UI can consume it', async () => {
    const target = database('document-corrupt')
    const targetDescriptor = descriptor()
    await target.documents.put({
      key: offlineDocumentKey(targetDescriptor),
      ownerId: targetDescriptor.ownerId,
      version: 'revision-one',
      cachedAt: NOW.toISOString(),
      payload: { schemaVersion: 1, payload: { title: 'Unchecked' } },
    })

    await expect(readOfflineDocument(target, targetDescriptor, payloadSchema)).resolves.toBeNull()
    expect(await target.documents.count()).toBe(0)
  })

  it('evicts the oldest owner records to stay inside the entry budget', async () => {
    const target = database('document-prune')
    for (const [index, resource] of ['first', 'second', 'third'].entries()) {
      await writeOfflineDocument(
        target,
        descriptor('account-student-one', resource),
        `revision-${resource}`,
        { title: resource, revision: index + 1 },
        payloadSchema,
        {
          now: () => new Date(NOW.getTime() + index * 1_000),
          maxEntries: 10,
        },
      )
    }

    expect(await pruneOfflineDocuments(target, 'account-student-one', { maxEntries: 2 })).toEqual(
      expect.objectContaining({ entries: 2 }),
    )
    await expect(
      readOfflineDocument(target, descriptor('account-student-one', 'first'), payloadSchema),
    ).resolves.toBeNull()
    expect((await offlineDocumentUsage(target, 'account-student-one')).entries).toBe(2)
  })
})
