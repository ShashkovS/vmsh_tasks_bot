import { describe, expect, it } from 'vitest'

import {
  createSupportDraftStore,
  supportDraftDescriptorSchema,
  type SupportDraftStorageError,
  type SupportDraftDescriptor,
} from './support-draft'
import { type LocalDraftStorage } from './test-answer-draft'

class MemoryStorage implements LocalDraftStorage {
  readonly #values = new Map<string, string>()
  failWrite = false

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
    if (this.failWrite) throw new DOMException('quota', 'QuotaExceededError')
    this.#values.set(key, value)
  }
}

const TIMES = [
  new Date('2026-07-29T09:00:00.000Z'),
  new Date('2026-07-29T09:01:00.000Z'),
  new Date('2026-07-29T09:02:00.000Z'),
]

function problemDescriptor(
  overrides: Partial<SupportDraftDescriptor> = {},
): SupportDraftDescriptor {
  return supportDraftDescriptorSchema.parse({
    ownerAccountId: 'account-student-one',
    target: {
      kind: 'new_problem_question',
      groupLessonId: 'lesson-41-beginner',
      problemId: 'problem-metric-number',
    },
    ...overrides,
  })
}

function clock(values = TIMES) {
  let index = 0
  return () => values[Math.min(index++, values.length - 1)]!
}

describe('private support local draft store', () => {
  it('restores a Student problem question with stable delivery identity after reload', () => {
    const storage = new MemoryStorage()
    const options = {
      now: clock(),
      createIdempotencyKey: () => 'support-idempotency-one',
    }
    const descriptor = problemDescriptor()
    const first = createSupportDraftStore(
      { audience: 'student', instance: 'agent' },
      storage,
      options,
    )

    const initial = first.save(descriptor, 'Не понимаю, почему здесь число делится на 7.')
    const updated = first.save(descriptor, 'Не понимаю переход после второй формулы.')
    const restored = createSupportDraftStore({ audience: 'student', instance: 'agent' }, storage, {
      createIdempotencyKey: () => 'must-not-replace-existing-key',
    }).load(descriptor)

    expect(initial.clientCreatedAt).toBe('2026-07-29T09:00:00.000Z')
    expect(updated).toMatchObject({
      text: 'Не понимаю переход после второй формулы.',
      idempotencyKey: 'support-idempotency-one',
      clientCreatedAt: initial.clientCreatedAt,
      updatedAt: '2026-07-29T09:01:00.000Z',
    })
    expect(restored).toEqual(updated)
  })

  it('isolates drafts by runtime, audience, account and target', () => {
    const storage = new MemoryStorage()
    const descriptor = problemDescriptor()
    const studentAgent = createSupportDraftStore(
      { audience: 'student', instance: 'agent' },
      storage,
      { createIdempotencyKey: () => 'student-agent-key' },
    )
    studentAgent.save(descriptor, 'Черновик школьника')

    expect(
      createSupportDraftStore({ audience: 'student', instance: 'human' }, storage).load(descriptor),
    ).toBeNull()
    expect(
      createSupportDraftStore({ audience: 'staff', instance: 'agent' }, storage).load(descriptor),
    ).toBeNull()
    expect(
      studentAgent.load(problemDescriptor({ ownerAccountId: 'account-student-two' })),
    ).toBeNull()
    expect(
      studentAgent.load({
        ownerAccountId: descriptor.ownerAccountId,
        target: { kind: 'existing_thread', threadId: 'support-thread-one' },
      }),
    ).toBeNull()
    expect(
      studentAgent.load({
        ownerAccountId: descriptor.ownerAccountId,
        target: {
          kind: 'new_general_question',
          groupLessonId: 'lesson-41-beginner',
        },
      }),
    ).toBeNull()
  })

  it('supports a compact Staff reply draft without inventing offline delivery', () => {
    const storage = new MemoryStorage()
    const descriptor: SupportDraftDescriptor = {
      ownerAccountId: 'account-teacher-one',
      target: { kind: 'existing_thread', threadId: 'support-thread-one' },
    }
    const store = createSupportDraftStore({ audience: 'staff', instance: 'agent' }, storage, {
      createIdempotencyKey: () => 'staff-reply-key',
    })

    expect(store.save(descriptor, 'Посмотрите на остатки по модулю 7.')).toMatchObject({
      audience: 'staff',
      ownerAccountId: 'account-teacher-one',
      target: { kind: 'existing_thread', threadId: 'support-thread-one' },
      idempotencyKey: 'staff-reply-key',
    })
  })

  it('removes corrupt or key-tampered data without touching another account', () => {
    const storage = new MemoryStorage()
    const store = createSupportDraftStore({ audience: 'student', instance: 'agent' }, storage, {
      createIdempotencyKey: () => 'draft-key',
    })
    const first = problemDescriptor()
    const second = problemDescriptor({ ownerAccountId: 'account-student-two' })
    store.save(first, 'Первый черновик')
    const secondDraft = store.save(second, 'Второй черновик')
    storage.setItem(store.key(first), '{broken')

    expect(store.load(first)).toBeNull()
    expect(storage.getItem(store.key(first))).toBeNull()
    expect(store.load(second)).toEqual(secondDraft)

    storage.setItem(
      store.key(first),
      JSON.stringify({
        ...secondDraft,
        ownerAccountId: first.ownerAccountId,
        target: { kind: 'existing_thread', threadId: 'support-thread-tampered' },
      }),
    )
    expect(store.load(first)).toBeNull()
    expect(store.load(second)).toEqual(secondDraft)
  })

  it('reports denied localStorage writes instead of claiming durability', () => {
    const storage = new MemoryStorage()
    storage.failWrite = true
    const store = createSupportDraftStore({ audience: 'student', instance: 'agent' }, storage, {
      createIdempotencyKey: () => 'denied-key',
    })

    expect(() => store.save(problemDescriptor(), 'Важный вопрос')).toThrowError(
      expect.objectContaining<Partial<SupportDraftStorageError>>({
        name: 'SupportDraftStorageError',
        operation: 'write',
      }),
    )
    expect(store.load(problemDescriptor())).toBeNull()
  })

  it('clears exactly one sent draft or all drafts for one signed-in account', () => {
    const storage = new MemoryStorage()
    const store = createSupportDraftStore({ audience: 'student', instance: 'agent' }, storage, {
      createIdempotencyKey: () => 'clear-key',
    })
    const first = problemDescriptor()
    const second: SupportDraftDescriptor = {
      ownerAccountId: first.ownerAccountId,
      target: { kind: 'existing_thread', threadId: 'support-thread-two' },
    }
    const other = problemDescriptor({ ownerAccountId: 'account-student-other' })
    store.save(first, 'Новая тема')
    store.save(second, 'Ответ в переписку')
    const otherDraft = store.save(other, 'Другой аккаунт')

    store.clear(first)
    expect(store.load(first)).toBeNull()
    expect(store.load(second)?.text).toBe('Ответ в переписку')

    store.clearOwner(first.ownerAccountId)
    expect(store.load(second)).toBeNull()
    expect(store.load(other)).toEqual(otherDraft)
  })
})
