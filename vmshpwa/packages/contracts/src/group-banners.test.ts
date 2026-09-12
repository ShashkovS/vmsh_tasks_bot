import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/group-banners/list.v1.json'
import { groupBannerListResponseSchema, saveGroupBannerRequestSchema } from './group-banners'

describe('group banner contracts', () => {
  it('parses the shared list fixture', () => {
    const parsed = groupBannerListResponseSchema.parse(fixture)
    expect(parsed.items.map((item) => item.audience)).toEqual(['both', 'student'])
  })

  it('rejects an inverted display window', () => {
    expect(() =>
      saveGroupBannerRequestSchema.parse({
        schemaVersion: 1,
        groupId: 'group-beginner',
        audience: 'student',
        html: '<b>Разбор</b>',
        startsAt: '2026-10-05T18:00:00Z',
        endsAt: '2026-10-05T17:00:00Z',
        priority: 0,
        dismissible: true,
      }),
    ).toThrow()
  })
})
