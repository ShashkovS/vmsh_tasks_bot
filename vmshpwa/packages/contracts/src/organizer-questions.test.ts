import { describe, expect, it } from 'vitest'
import { organizerSendSchema, organizerPhotoSchema } from './organizer-questions'
describe('organizer contracts', () => {
  const base = { text: 'Вопрос', photoIds: [], childId: null, idempotencyKey: 'once' }
  it('accepts independent and photo-only questions', () => {
    expect(organizerSendSchema.parse(base)).toEqual(base)
    expect(organizerSendSchema.safeParse({ ...base, text: '', photoIds: ['oqp-1'] }).success).toBe(
      true,
    )
  })
  it('rejects empty messages, too many photos, author injection and unsafe media URLs', () => {
    for (const bad of [
      { ...base, text: ' ' },
      { ...base, photoIds: Array(11).fill('oqp-1') },
      { ...base, accountId: 'other' },
    ])
      expect(organizerSendSchema.safeParse(bad).success).toBe(false)
    expect(
      organizerPhotoSchema.safeParse({
        photoId: 'oqp-1',
        width: 2,
        height: 2,
        url: 'https://external.invalid/private',
      }).success,
    ).toBe(false)
  })
})
