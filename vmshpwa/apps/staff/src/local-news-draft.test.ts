import { describe, expect, it } from 'vitest'

import {
  EMPTY_LOCAL_NEWS_DRAFT,
  clearLocalNewsDraft,
  loadLocalNewsDraft,
  moscowDateTime,
  saveLocalNewsDraft,
  toMoscowLocalDateTime,
} from './local-news-draft'

function memoryStorage(): Storage {
  const values = new Map<string, string>()
  return {
    get length() {
      return values.size
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => void values.delete(key),
    setItem: (key, value) => values.set(key, value),
  }
}

describe('local news draft', () => {
  it('survives reload and clears only after receipt', () => {
    const storage = memoryStorage()
    const key = 'test:local-news-draft'
    clearLocalNewsDraft(storage, key)
    const draft = {
      owner: 'group:group.beginners',
      text: 'Разбор в 17:00',
      publishedLocal: '2026-08-04T17:00',
    }
    saveLocalNewsDraft(storage, key, draft)
    expect(loadLocalNewsDraft(storage, key)).toEqual(draft)
    clearLocalNewsDraft(storage, key)
    expect(loadLocalNewsDraft(storage, key)).toEqual(EMPTY_LOCAL_NEWS_DRAFT)
  })

  it('rejects corrupted browser state and converts Moscow wall time', () => {
    const storage = memoryStorage()
    storage.setItem('test:bad-local-news-draft', '{bad')
    expect(loadLocalNewsDraft(storage, 'test:bad-local-news-draft')).toEqual(EMPTY_LOCAL_NEWS_DRAFT)
    expect(moscowDateTime('2026-08-04T17:00')).toBe('2026-08-04T14:00:00.000Z')
    expect(moscowDateTime('tomorrow')).toBeNull()
    expect(toMoscowLocalDateTime('2026-08-04T14:00:00Z')).toBe('2026-08-04T17:00')
    expect(toMoscowLocalDateTime('tomorrow')).toBeNull()
  })
})
