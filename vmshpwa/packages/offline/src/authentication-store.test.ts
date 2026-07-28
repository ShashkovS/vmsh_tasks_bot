import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it } from 'vitest'

import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import { authContextSchema } from '@vmsh/contracts'

import { createOfflineAuthenticationStore } from './authentication-store'
import {
  VmshOfflineDatabase,
  type CachedDocument,
  type OutboxItem,
  type WrittenDraftPhotoRecord,
} from './database'

const databases = new Set<VmshOfflineDatabase>()
const NOW = new Date('2026-07-28T10:00:00.000Z')

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

function context(ownerId = studentAuthFixture.authContext.principal.accountId) {
  return authContextSchema.parse({
    ...studentAuthFixture.authContext,
    principal: { ...studentAuthFixture.authContext.principal, accountId: ownerId },
  })
}

function document(ownerId: string): CachedDocument {
  return {
    key: `condition:${ownerId}`,
    ownerId,
    version: 'revision-1',
    cachedAt: NOW.toISOString(),
    payload: { statement: 'Сохранённое условие' },
  }
}

function outbox(ownerId: string): OutboxItem {
  return {
    id: `outbox-${ownerId}`,
    idempotencyKey: `idempotency-${ownerId}`,
    ownerId,
    kind: 'written-answer',
    createdAtClient: NOW.toISOString(),
    updatedAtClient: NOW.toISOString(),
    timezoneOffsetMinutes: -180,
    payloadHash: `sha256:${ownerId}`,
    status: 'queued',
    attempts: 0,
    payload: { text: 'Черновик' },
  }
}

function photo(ownerId: string): WrittenDraftPhotoRecord {
  const bytes = new TextEncoder().encode('photo')
  return {
    id: `photo-${ownerId}`,
    draftKey: `draft-${ownerId}`,
    ownerId,
    problemId: 'problem-written',
    conditionRevisionId: 'condition-revision-one',
    configVersion: 1,
    fileName: 'page.webp',
    mediaType: 'image/webp',
    byteSize: bytes.byteLength,
    width: 100,
    height: 100,
    processing: 'client-webp',
    createdAt: NOW.toISOString(),
    updatedAt: NOW.toISOString(),
    bytes: bytes.buffer,
  }
}

describe('offline authentication store', () => {
  it('persists only a secret-free owner snapshot and reads it before expiry', async () => {
    const target = database('auth-snapshot')
    const store = createOfflineAuthenticationStore(target, 'student', { now: () => NOW })
    const authenticated = context()

    const snapshot = await store.save(authenticated)
    const stored = await target.authentication.get('current')

    expect(await store.read()).toEqual(snapshot)
    expect(snapshot).toMatchObject({
      audience: 'student',
      ownerId: authenticated.principal.accountId,
      principal: authenticated.principal,
      sessionExpiresAt: authenticated.policy.sessionExpiresAt,
    })
    const serialized = JSON.stringify(stored?.payload)
    expect(serialized).not.toContain(authenticated.currentSession.sessionId)
    expect(serialized).not.toContain('telegramToken')
    expect(serialized).not.toContain('password')
  })

  it('fails closed and clears owner data when the durable boundary expired', async () => {
    const target = database('auth-expired')
    const online = new Date('2026-07-27T10:00:00.000Z')
    const store = createOfflineAuthenticationStore(target, 'student', { now: () => online })
    const authenticated = context()
    const ownerId = authenticated.principal.accountId
    await store.save(authenticated)
    await Promise.all([
      target.documents.put(document(ownerId)),
      target.outbox.put(outbox(ownerId)),
      target.writtenDraftPhotos.put(photo(ownerId)),
    ])

    const afterExpiry = createOfflineAuthenticationStore(target, 'student', {
      now: () => new Date('2026-08-10T00:00:00.000Z'),
    })
    await expect(afterExpiry.read()).resolves.toBeNull()
    expect(await target.authentication.count()).toBe(0)
    expect(await target.documents.where('ownerId').equals(ownerId).count()).toBe(0)
    expect(await target.outbox.where('ownerId').equals(ownerId).count()).toBe(0)
    expect(await target.writtenDraftPhotos.where('ownerId').equals(ownerId).count()).toBe(0)
  })

  it('atomically removes the previous owner cache on an account switch', async () => {
    const target = database('auth-switch')
    const store = createOfflineAuthenticationStore(target, 'student', { now: () => NOW })
    const oldOwner = context().principal.accountId
    const newOwner = 'account-student-second'
    await store.save(context(oldOwner))
    await Promise.all([
      target.documents.put(document(oldOwner)),
      target.outbox.put(outbox(oldOwner)),
      target.writtenDraftPhotos.put(photo(oldOwner)),
      target.documents.put(document(newOwner)),
    ])

    await store.save(context(newOwner))

    expect((await store.read())?.ownerId).toBe(newOwner)
    expect(await target.documents.where('ownerId').equals(oldOwner).count()).toBe(0)
    expect(await target.outbox.where('ownerId').equals(oldOwner).count()).toBe(0)
    expect(await target.writtenDraftPhotos.where('ownerId').equals(oldOwner).count()).toBe(0)
    expect(await target.documents.where('ownerId').equals(newOwner).count()).toBe(1)
  })

  it('clears the current owner only after an explicit confirmed end', async () => {
    const target = database('auth-clear')
    const store = createOfflineAuthenticationStore(target, 'student', { now: () => NOW })
    const ownerId = context().principal.accountId
    await store.save(context())
    await Promise.all([
      target.documents.put(document(ownerId)),
      target.outbox.put(outbox(ownerId)),
      target.writtenDraftPhotos.put(photo(ownerId)),
    ])

    await store.clear()

    expect(await store.read()).toBeNull()
    expect(await target.documents.count()).toBe(0)
    expect(await target.outbox.count()).toBe(0)
    expect(await target.writtenDraftPhotos.count()).toBe(0)
  })

  it('rejects a context from another audience', async () => {
    const target = database('auth-audience')
    const familyStore = createOfflineAuthenticationStore(target, 'family', { now: () => NOW })
    await expect(familyStore.save(context())).rejects.toThrow('audience')
    expect(await target.authentication.count()).toBe(0)
  })
})
