import { describe, expect, it } from 'vitest'

import {
  TestAnswerDraftStorageError,
  createTestAnswerDraftStore,
  type LocalDraftStorage,
  type TestAnswerDraftDescriptor,
} from './test-answer-draft'

const NOW = new Date('2026-07-28T13:00:00.000Z')

class MemoryStorage implements LocalDraftStorage {
  readonly #values = new Map<string, string>()

  get length() {
    return this.#values.size
  }

  getItem(key: string) {
    return this.#values.get(key) ?? null
  }

  key(index: number) {
    return [...this.#values.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.#values.delete(key)
  }

  setItem(key: string, value: string) {
    this.#values.set(key, value)
  }
}

function descriptor(overrides: Partial<TestAnswerDraftDescriptor> = {}): TestAnswerDraftDescriptor {
  return {
    ownerId: 'account-student-one',
    problemId: 'problem-fraction',
    conditionRevisionId: 'condition-revision-one',
    configVersion: 3,
    ...overrides,
  }
}

function store(storage: LocalDraftStorage, instance = 'agent') {
  return createTestAnswerDraftStore({ audience: 'student', instance }, storage, {
    now: () => NOW,
  })
}

describe('test-answer local draft store', () => {
  it('restores an exact account/problem/revision draft after a new store instance', () => {
    const storage = new MemoryStorage()
    store(storage).save(descriptor(), '7/3')

    const restored = store(storage).load(descriptor())

    expect(restored.compatible).toMatchObject({
      displayAnswer: '7/3',
      updatedAt: NOW.toISOString(),
      namespace: 'vmsh-179:v1:student:agent',
    })
    expect(restored.incompatible).toEqual([])
  })

  it('does not expose drafts across accounts or runtime instances', () => {
    const storage = new MemoryStorage()
    store(storage).save(descriptor(), '179')

    expect(store(storage).load(descriptor({ ownerId: 'account-student-two' }))).toEqual({
      compatible: null,
      incompatible: [],
    })
    expect(store(storage, 'human').load(descriptor())).toEqual({
      compatible: null,
      incompatible: [],
    })
  })

  it('reports an old revision as incompatible and never overwrites it', () => {
    const storage = new MemoryStorage()
    const target = store(storage)
    target.save(descriptor(), 'старый ответ')

    const nextRevision = descriptor({
      conditionRevisionId: 'condition-revision-two',
      configVersion: 4,
    })
    expect(target.load(nextRevision)).toMatchObject({
      compatible: null,
      incompatible: [{ displayAnswer: 'старый ответ', configVersion: 3 }],
    })

    target.save(nextRevision, 'новый ответ')
    expect(target.load(nextRevision)).toMatchObject({
      compatible: { displayAnswer: 'новый ответ' },
      incompatible: [{ displayAnswer: 'старый ответ' }],
    })
    expect(storage.length).toBe(2)
  })

  it('clears only the acknowledged revision and can explicitly clear one owner', () => {
    const storage = new MemoryStorage()
    const target = store(storage)
    const first = descriptor()
    const second = descriptor({ conditionRevisionId: 'condition-revision-two' })
    target.save(first, 'первый')
    target.save(second, 'второй')
    target.save(descriptor({ ownerId: 'account-student-two' }), 'чужой')

    target.clear(second)
    expect(target.load(first).compatible?.displayAnswer).toBe('первый')
    expect(target.load(second).compatible).toBeNull()

    target.clearOwner(first.ownerId)
    expect(storage.length).toBe(1)
    expect(
      target.load(descriptor({ ownerId: 'account-student-two' })).compatible?.displayAnswer,
    ).toBe('чужой')
  })

  it('removes malformed records instead of returning unchecked content', () => {
    const storage = new MemoryStorage()
    const target = store(storage)
    storage.setItem(target.key(descriptor()), '{not-json')

    expect(target.load(descriptor())).toEqual({ compatible: null, incompatible: [] })
    expect(storage.length).toBe(0)
  })

  it('surfaces quota failures so the UI cannot claim that work was saved', () => {
    const quotaError = new DOMException('Storage full', 'QuotaExceededError')
    const storage = new MemoryStorage()
    storage.setItem = () => {
      throw quotaError
    }

    let thrown: unknown
    try {
      store(storage).save(descriptor(), 'важный ответ')
    } catch (error) {
      thrown = error
    }
    expect(thrown).toBeInstanceOf(TestAnswerDraftStorageError)
    expect(thrown).toMatchObject({
      name: 'TestAnswerDraftStorageError',
      operation: 'write',
      cause: quotaError,
    })
  })
})
