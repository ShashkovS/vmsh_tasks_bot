import { describe, expect, it } from 'vitest'
import { textOriginSchema } from './paste-evidence'

describe('packed text origin contract', () => {
  it('accepts empty and populated canonical masks', () => {
    expect(textOriginSchema.parse({ version: 1, utf16Length: 0, bits: '' }).bits).toBe('')
    expect(textOriginSchema.parse({ version: 1, utf16Length: 2, bits: 'Aw==' }).utf16Length).toBe(2)
  })
  it.each(['!', 'AA=', '////', '/w==', 'AB=='])(
    'rejects invalid bytes, padding or trailing bits: %s',
    (bits) => {
      expect(textOriginSchema.safeParse({ version: 1, utf16Length: 2, bits }).success).toBe(false)
    },
  )
})
