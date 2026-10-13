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

  it('validates course-wide attendance targeting', () => {
    const parsed = saveGroupBannerRequestSchema.parse({
      schemaVersion: 3,
      courseId: 'course.math',
      groupId: null,
      audience: 'family',
      attendanceMode: 'online',
      markdown: 'Онлайн-встреча',
      document: {
        schemaVersion: 1,
        media: [],
        blocks: [
          {
            type: 'paragraph',
            children: [{ type: 'text', text: 'Онлайн-встреча' }],
          },
        ],
      },
      startsAt: '2026-10-05T17:00:00Z',
      endsAt: '2026-10-05T18:00:00Z',
      priority: 0,
      dismissible: true,
    })
    expect(parsed).toMatchObject({ groupId: null, attendanceMode: 'online' })
  })
})
