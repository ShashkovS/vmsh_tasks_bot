import { describe, expect, it } from 'vitest'

import {
  dateTimeFormat,
  formatDate,
  formatDateTime,
  formatNumber,
  formatTime,
  formattersFor,
  numberFormat,
} from './formatters'

// Cached Intl formatters: see docs/i18n.md («Даты, числа, время»).
describe('locale formatters', () => {
  const moment = new Date('2026-09-18T09:05:00Z')
  const options: Intl.DateTimeFormatOptions = {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }

  it('reuses one formatter per locale and equal options', () => {
    expect(dateTimeFormat('ru', { ...options })).toBe(dateTimeFormat('ru', { ...options }))
    expect(dateTimeFormat('en', options)).not.toBe(dateTimeFormat('ru', options))
    expect(numberFormat('en')).toBe(numberFormat('en'))
  })

  it('formats in the interface language with the business timezone', () => {
    expect(formattersFor('ru').formatDateTime(moment, options)).toBe('18 сентября в 12:05')
    // ICU separates the day period with a narrow no-break space.
    expect(formattersFor('en').formatDateTime(moment, options).replace(/\s/g, ' ')).toBe(
      'September 18 at 12:05 PM',
    )
  })

  it('formats numbers, relative time and lists per language', () => {
    const russian = formattersFor('ru')
    const english = formattersFor('en')
    // Russian groups digits with a no-break space.
    expect(russian.formatNumber(1234.5).replace(/\s/g, ' ')).toBe('1 234,5')
    expect(english.formatNumber(1234.5)).toBe('1,234.5')
    expect(english.formatRelativeTime(-2, 'day', { numeric: 'auto' })).toBe('2 days ago')
    expect(english.formatList(['a', 'b', 'c'])).toBe('a, b, and c')
  })
})

describe('toLocale*String replacements', () => {
  const moment = new Date('2026-09-18T09:05:07Z')
  const moscow = { timeZone: 'Europe/Moscow' } as const

  it('keep the default fields of the replaced Date methods', () => {
    expect(formatDateTime(moment, moscow)).toBe(moment.toLocaleString('ru-RU', moscow))
    expect(formatDate(moment, moscow)).toBe(moment.toLocaleDateString('ru-RU', moscow))
    expect(formatTime(moment, moscow)).toBe(moment.toLocaleTimeString('ru-RU', moscow))
    const dayOnly = { ...moscow, day: 'numeric', month: 'long' } as const
    expect(formatDateTime(moment, dayOnly)).toBe(moment.toLocaleString('ru-RU', dayOnly))
    expect(formatDateTime(moment.toISOString(), { ...moscow, dateStyle: 'medium' })).toBe(
      moment.toLocaleString('ru-RU', { ...moscow, dateStyle: 'medium' }),
    )
  })

  it('formats numbers like Number#toLocaleString', () => {
    expect(formatNumber(1234.56, { maximumFractionDigits: 1 })).toBe(
      (1234.56).toLocaleString('ru-RU', { maximumFractionDigits: 1 }),
    )
  })
})
