import { describe, expect, it } from 'vitest'

import {
  convertWallTime,
  courseZoneHint,
  formatMomentForViewer,
  instantToWallTime,
  timeZoneShortName,
  wallTimeToInstant,
} from './time-zones'

// Policy: vmshpwa/dev/ui-audit-20261104/BACKLOG.md («Часовые пояса»).
describe('time-zone helpers', () => {
  it('round-trips wall time and instants in a fixed and a DST zone', () => {
    expect(wallTimeToInstant('2026-11-08T19:00', 'Europe/Moscow')?.toISOString()).toBe(
      '2026-11-08T16:00:00.000Z',
    )
    expect(instantToWallTime('2026-11-08T16:00:00Z', 'Asia/Nicosia')).toBe('2026-11-08T18:00')
    // Nicosia is UTC+3 in summer and UTC+2 in winter.
    expect(wallTimeToInstant('2026-07-01T12:00', 'Asia/Nicosia')?.toISOString()).toBe(
      '2026-07-01T09:00:00.000Z',
    )
    expect(instantToWallTime('2026-03-29T03:30:00Z', 'Europe/London')).toBe('2026-03-29T04:30')
  })

  it('converts a browser wall time to course wall time and back', () => {
    expect(convertWallTime('2026-11-08T18:00', 'Asia/Nicosia', 'Europe/Moscow')).toBe(
      '2026-11-08T19:00',
    )
    expect(convertWallTime('2026-11-08T19:00', 'Europe/Moscow', 'Asia/Nicosia')).toBe(
      '2026-11-08T18:00',
    )
    expect(convertWallTime('2026-11-08T23:30', 'Asia/Nicosia', 'Asia/Vladivostok')).toBe(
      '2026-11-09T07:30',
    )
    expect(convertWallTime('', 'Asia/Nicosia', 'Europe/Moscow')).toBe('')
    expect(convertWallTime('2026-11-08T19:00', 'Europe/Moscow', 'Europe/Moscow')).toBe(
      '2026-11-08T19:00',
    )
  })

  it('adds the course time only when zones differ', () => {
    const moment = '2026-11-08T16:00:00Z'
    expect(courseZoneHint(moment, 'Europe/Moscow', 'Europe/Moscow', 'ru')).toBeNull()
    // Same offset in winter: no hint.
    expect(courseZoneHint(moment, 'Europe/Moscow', 'Europe/Istanbul', 'ru')).toBeNull()
    expect(courseZoneHint(moment, 'Europe/Moscow', 'Asia/Nicosia', 'ru')).toBe('19:00 МСК')
    expect(
      courseZoneHint('2026-11-08T22:30:00Z', 'Europe/Moscow', 'America/New_York', 'ru'),
    ).toMatch(/^9 нояб\.?, 01:30 МСК$/)
  })

  it('formats a moment for the viewer with the course hint', () => {
    const options: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' }
    expect(
      formatMomentForViewer('2026-11-08T16:00:00Z', options, 'Europe/Moscow', 'Asia/Nicosia', 'ru'),
    ).toBe('18:00 (19:00 МСК)')
    expect(
      formatMomentForViewer(
        '2026-11-08T16:00:00Z',
        options,
        'Europe/Moscow',
        'Europe/Moscow',
        'ru',
      ),
    ).toBe('19:00')
  })

  it('names Moscow MSK and other zones by offset', () => {
    expect(timeZoneShortName('Europe/Moscow', new Date(), 'ru')).toBe('МСК')
    expect(timeZoneShortName('Europe/Moscow', new Date(), 'en')).toBe('MSK')
    expect(timeZoneShortName('Asia/Nicosia', new Date('2026-11-08T16:00:00Z'), 'ru')).toMatch(/\+2/)
  })
})
