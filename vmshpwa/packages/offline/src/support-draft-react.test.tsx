import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useSupportDraftEditor } from './support-draft-react'
import { type SupportDraftDescriptor } from './support-draft'
import { type LocalDraftStorage } from './test-answer-draft'

class MemoryStorage implements LocalDraftStorage {
  readonly values = new Map<string, string>()
  failWrite = false

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
    if (this.failWrite) throw new DOMException('quota', 'QuotaExceededError')
    this.values.set(key, value)
  }
}

const descriptor: SupportDraftDescriptor = {
  ownerAccountId: 'account-student-hook',
  target: { kind: 'existing_thread', threadId: 'support-thread-hook' },
}

describe('support draft React binding', () => {
  it('survives an unmount and clears only after confirmed delivery', () => {
    const storage = new MemoryStorage()
    const options = {
      storage,
      now: () => new Date('2026-07-29T10:00:00.000Z'),
      createIdempotencyKey: () => 'support-hook-key',
    }
    const first = renderHook(() =>
      useSupportDraftEditor({ audience: 'student', instance: 'agent' }, descriptor, options),
    )
    act(() => first.result.current.setText('Сохранённый вопрос'))
    expect(first.result.current).toMatchObject({
      text: 'Сохранённый вопрос',
      saveState: 'saved',
      delivery: {
        idempotencyKey: 'support-hook-key',
        clientCreatedAt: '2026-07-29T10:00:00.000Z',
      },
    })
    first.unmount()

    const restored = renderHook(() =>
      useSupportDraftEditor({ audience: 'student', instance: 'agent' }, descriptor, options),
    )
    expect(restored.result.current.text).toBe('Сохранённый вопрос')
    act(() => restored.result.current.clearAfterConfirmedSend())
    expect(restored.result.current).toMatchObject({ text: '', saveState: 'idle' })
    restored.unmount()

    const afterSend = renderHook(() =>
      useSupportDraftEditor({ audience: 'student', instance: 'agent' }, descriptor, options),
    )
    expect(afterSend.result.current.text).toBe('')
  })

  it('keeps an in-memory delivery identity and warns when persistence is unavailable', () => {
    const storage = new MemoryStorage()
    storage.failWrite = true
    const editor = renderHook(() =>
      useSupportDraftEditor({ audience: 'staff', instance: 'agent' }, descriptor, {
        storage,
        now: () => new Date('2026-07-29T10:05:00.000Z'),
        createIdempotencyKey: () => 'support-memory-key',
      }),
    )

    act(() => editor.result.current.setText('Ответ всё равно можно отправить'))
    expect(editor.result.current).toMatchObject({
      text: 'Ответ всё равно можно отправить',
      saveState: 'unavailable',
      delivery: {
        idempotencyKey: 'support-memory-key',
        clientCreatedAt: '2026-07-29T10:05:00.000Z',
      },
    })
    expect(editor.result.current.storageError).toBeInstanceOf(Error)
  })
})
