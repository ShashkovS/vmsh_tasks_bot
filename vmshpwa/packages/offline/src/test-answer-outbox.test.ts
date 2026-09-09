import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it, vi } from 'vitest'

import mutationFixture from '@vmsh/contracts/fixtures/submissions/mutation.v1.json'
import { ApiResponseError, submitTestAnswerResponseSchema } from '@vmsh/contracts'

import { VmshOfflineDatabase } from './database'
import { createTestAnswerOutbox } from './test-answer-outbox'

const databases = new Set<VmshOfflineDatabase>()
const NOW = new Date(mutationFixture.request.clientCreatedAt)
const UUID = mutationFixture.request.idempotencyKey
const HASH = `sha256:${'a'.repeat(64)}`
const RECEIPT = submitTestAnswerResponseSchema.parse(mutationFixture.response)

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

function outbox(target: VmshOfflineDatabase, ownerId = 'account-student-one') {
  return createTestAnswerOutbox(target, ownerId, {
    now: () => NOW,
    randomUUID: () => UUID,
    payloadHasher: () => Promise.resolve(HASH),
  })
}

function enqueue(target: ReturnType<typeof outbox>) {
  return target.enqueue({
    problemId: mutationFixture.response.problemId,
    problemRevision: mutationFixture.request.problemRevision,
    displayAnswer: mutationFixture.request.displayAnswer,
    timezoneOffsetMinutes: -180,
  })
}

describe('test-answer Dexie outbox', () => {
  it('persists one immutable versioned wire request and its client timestamp', async () => {
    const target = database('test-answer-enqueue')
    const queue = outbox(target)

    const item = await enqueue(queue)

    expect(item).toMatchObject({
      id: UUID,
      idempotencyKey: UUID,
      ownerId: 'account-student-one',
      kind: 'test-answer',
      createdAtClient: mutationFixture.request.clientCreatedAt,
      timezoneOffsetMinutes: -180,
      payloadHash: HASH,
      status: 'queued',
      attempts: 0,
      payload: {
        problemId: mutationFixture.response.problemId,
        request: mutationFixture.request,
      },
    })
    expect(await queue.list()).toEqual([item])
  })

  it('claims once across concurrent flushers, stores the receipt, then acknowledges it', async () => {
    const target = database('test-answer-concurrent')
    const queue = outbox(target)
    await enqueue(queue)
    const submit = vi.fn(() => Promise.resolve(RECEIPT))

    const results = await Promise.all([
      queue.deliverNext({ submit }),
      queue.deliverNext({ submit }),
    ])

    expect(submit).toHaveBeenCalledOnce()
    expect(results.map((result) => result.state).sort()).toEqual(['idle', 'synced'])
    expect((await queue.list())[0]).toMatchObject({
      status: 'synced',
      attempts: 1,
      result: RECEIPT,
    })
    expect(await queue.acknowledge(UUID)).toBe(true)
    expect(await queue.list()).toEqual([])
    expect(await queue.acknowledge(UUID)).toBe(false)
  })

  it('keeps a byte-equivalent retryable request after network failure', async () => {
    const target = database('test-answer-retry')
    const queue = outbox(target)
    const original = await enqueue(queue)
    const offline = new TypeError('offline')

    const failed = await queue.deliverNext({ submit: () => Promise.reject(offline) })
    expect(failed).toMatchObject({ state: 'retrying' })
    const stored = (await queue.list())[0]
    expect(stored).toMatchObject({
      status: 'retrying',
      attempts: 1,
      payload: original.payload,
      payloadHash: original.payloadHash,
      lastError: 'client:TypeError',
    })

    const submit = vi.fn(() => Promise.resolve(RECEIPT))
    await expect(queue.deliverNext({ submit })).resolves.toMatchObject({ state: 'synced' })
    expect(submit).toHaveBeenCalledWith(mutationFixture.response.problemId, mutationFixture.request)
  })

  it('retains revision and idempotency conflicts for explicit resolution', async () => {
    const target = database('test-answer-conflict')
    const queue = outbox(target)
    await enqueue(queue)
    const conflict = new ApiResponseError(409, {
      error: {
        code: 'test_problem_revision_changed',
        message: 'Условие изменилось',
        requestId: 'request-conflict',
      },
    })

    await expect(
      queue.deliverNext({ submit: () => Promise.reject(conflict) }),
    ).resolves.toMatchObject({ state: 'conflict' })
    expect((await queue.list())[0]).toMatchObject({
      status: 'conflict',
      payload: { request: mutationFixture.request },
      lastError: 'api:409:test_problem_revision_changed:request=request-conflict',
    })
    expect(await queue.acknowledge(UUID)).toBe(false)
  })

  it('reclaims a crashed sending lease with the same UUID and payload', async () => {
    const target = database('test-answer-crash-recovery')
    const queue = outbox(target)
    const original = await enqueue(queue)
    await target.outbox.update(original.id, {
      status: 'sending',
      attempts: 1,
      updatedAtClient: new Date(NOW.getTime() - 60_001).toISOString(),
    })
    const submit = vi.fn(() => Promise.resolve(RECEIPT))

    await expect(queue.deliverNext({ submit })).resolves.toMatchObject({ state: 'synced' })

    expect(submit).toHaveBeenCalledExactlyOnceWith(original.payload.problemId, {
      ...original.payload.request,
      idempotencyKey: original.idempotencyKey,
    })
    expect((await queue.list())[0]).toMatchObject({
      status: 'synced',
      attempts: 2,
      idempotencyKey: original.idempotencyKey,
      payloadHash: original.payloadHash,
    })
  })

  it('does not let one owner deliver or acknowledge another owner queue', async () => {
    const target = database('test-answer-owner')
    const first = outbox(target, 'account-student-one')
    await enqueue(first)
    const second = outbox(target, 'account-student-two')

    await expect(second.deliverNext({ submit: () => Promise.resolve(RECEIPT) })).resolves.toEqual({
      state: 'idle',
    })
    expect(await second.acknowledge(UUID)).toBe(false)
    expect((await first.list())[0]?.status).toBe('queued')
  })
})
