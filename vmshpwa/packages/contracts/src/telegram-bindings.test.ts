import fixture from '../fixtures/telegram-bindings/list.v1.json'

import { describe, expect, it } from 'vitest'

import {
  saveTelegramBindingRequestSchema,
  telegramBindingOwnersResponseSchema,
  telegramBindingListResponseSchema,
  telegramBindingSchema,
} from './telegram-bindings'

describe('telegram binding contracts', () => {
  it('parses the versioned course/group fixture', () => {
    const parsed = telegramBindingListResponseSchema.parse(fixture)
    expect(parsed.items.map((item) => item.status)).toEqual(['verified', 'draft'])
    expect(parsed.items[1]?.messageThreadId).toBe(179)
  })

  it('requires verification time for a verified binding', () => {
    expect(() => telegramBindingSchema.parse({ ...fixture.items[0], verifiedAt: null })).toThrow()
  })

  it('rejects an unsafe or zero destination before HTTP', () => {
    const request = {
      schemaVersion: 1,
      ownerType: 'course',
      ownerId: 'course.math-5-7',
      purpose: 'news_source',
      chatId: 0,
      messageThreadId: null,
      titleCached: null,
    }
    expect(() => saveTelegramBindingRequestSchema.parse(request)).toThrow()
    expect(() =>
      saveTelegramBindingRequestSchema.parse({ ...request, chatId: Number.MAX_VALUE }),
    ).toThrow()
  })

  it('validates selectable course and group owners', () => {
    const parsed = telegramBindingOwnersResponseSchema.parse({
      schemaVersion: 1,
      courses: [
        {
          courseId: 'course.math-5-7',
          courseName: 'Математика 5–7',
          status: 'active',
          groups: [{ groupId: 'group.beginner', groupName: 'Начинающие', status: 'active' }],
        },
      ],
      requestId: 'owners-fixture',
    })
    expect(parsed.courses[0]?.groups[0]?.groupId).toBe('group.beginner')
  })
})
