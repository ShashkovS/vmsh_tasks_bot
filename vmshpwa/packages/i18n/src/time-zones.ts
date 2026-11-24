import { currentLocale } from './activation'
import { dateTimeFormat } from './formatters'
import type { Locale } from './locale'

/**
 * Time-zone policy (vmshpwa/dev/ui-audit-20261104/BACKLOG.md, «Часовые пояса»):
 * - every person reads and types one-off moments (deadlines, publications, windows,
 *   events) in the time zone of their own browser;
 * - the server keeps lesson times as wall time in the course business zone, so staff
 *   inputs are converted with these helpers before they are sent;
 * - when the browser zone differs from the course zone, the UI adds the course time
 *   («19:00 МСК») so students and teachers can still agree on the same number;
 * - recurring course schedule rules stay in the course zone.
 *
 * Wall times use the `<input type="datetime-local">` shape `YYYY-MM-DDTHH:mm`.
 */

export const DEFAULT_COURSE_TIME_ZONE = 'Europe/Moscow'

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

const partFormats = new Map<string, Intl.DateTimeFormat>()

function wallParts(instant: Date, timeZone: string) {
  let format = partFormats.get(timeZone)
  if (!format) {
    format = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    partFormats.set(timeZone, format)
  }
  const parts: Record<string, number> = {}
  for (const part of format.formatToParts(instant)) {
    if (part.type !== 'literal') parts[part.type] = Number(part.value)
  }
  return {
    year: parts.year ?? 1970,
    month: parts.month ?? 1,
    day: parts.day ?? 1,
    hour: (parts.hour ?? 0) % 24,
    minute: parts.minute ?? 0,
    second: parts.second ?? 0,
  }
}

/** Offset of `timeZone` from UTC at `instant`, in milliseconds (Moscow → +3 h). */
export function timeZoneOffsetMs(instant: Date, timeZone: string): number {
  const p = wallParts(instant, timeZone)
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second)
  return asUtc - Math.floor(instant.getTime() / 1000) * 1000
}

const pad = (value: number) => String(value).padStart(2, '0')

/** The wall time shown by a clock in `timeZone` at `instant`. */
export function instantToWallTime(instant: Date | string, timeZone: string): string {
  const date = typeof instant === 'string' ? new Date(instant) : instant
  if (Number.isNaN(date.getTime())) return ''
  const p = wallParts(date, timeZone)
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`
}

function parseWallTime(wall: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(wall)
  if (!match) return null
  const [, y, m, d, h, mi] = match.map(Number) as [number, number, number, number, number, number]
  return Date.UTC(y, m - 1, d, h, mi)
}

/** The instant at which a clock in `timeZone` shows `wall`. */
export function wallTimeToInstant(wall: string, timeZone: string): Date | null {
  const asUtc = parseWallTime(wall)
  if (asUtc === null) return null
  // Two passes settle the offset, including around daylight-saving transitions.
  let guess = asUtc - timeZoneOffsetMs(new Date(asUtc), timeZone)
  guess = asUtc - timeZoneOffsetMs(new Date(guess), timeZone)
  return new Date(guess)
}

/** Re-express a wall time from one zone in another (browser input → course wall time). */
export function convertWallTime(wall: string, fromZone: string, toZone: string): string {
  if (!wall) return ''
  if (fromZone === toZone) return wall.slice(0, 16)
  const instant = wallTimeToInstant(wall, fromZone)
  return instant ? instantToWallTime(instant, toZone) : ''
}

export function zonesDifferAt(instant: Date, left: string, right: string): boolean {
  return left !== right && timeZoneOffsetMs(instant, left) !== timeZoneOffsetMs(instant, right)
}

/** Short zone name: «МСК» for Moscow, otherwise the locale's offset name («GMT+2»). */
export function timeZoneShortName(
  timeZone: string,
  instant: Date = new Date(),
  locale: Locale = currentLocale(),
): string {
  // Established abbreviation per interface language, not translatable copy.
  // eslint-disable-next-line lingui/no-unlocalized-strings
  if (timeZone === 'Europe/Moscow') return locale === 'ru' ? 'МСК' : 'MSK'
  const name = dateTimeFormat(locale, { timeZone, timeZoneName: 'shortOffset' })
    .formatToParts(instant)
    .find((part) => part.type === 'timeZoneName')?.value
  return name ?? timeZone
}

/**
 * The course-zone equivalent of a moment, e.g. «19:00 МСК» (or «8 нояб., 19:00 МСК»
 * when the date differs too), or null when the viewer is already in the course zone.
 */
export function courseZoneHint(
  instant: Date | string,
  courseTimeZone: string,
  viewerTimeZone: string = browserTimeZone(),
  locale: Locale = currentLocale(),
): string | null {
  const date = typeof instant === 'string' ? new Date(instant) : instant
  if (Number.isNaN(date.getTime())) return null
  if (!zonesDifferAt(date, viewerTimeZone, courseTimeZone)) return null
  const sameDay =
    instantToWallTime(date, viewerTimeZone).slice(0, 10) ===
    instantToWallTime(date, courseTimeZone).slice(0, 10)
  const time = dateTimeFormat(locale, {
    ...(sameDay ? {} : { day: 'numeric', month: 'short' }),
    hour: '2-digit',
    minute: '2-digit',
    timeZone: courseTimeZone,
  }).format(date)
  return `${time} ${timeZoneShortName(courseTimeZone, date, locale)}`
}

/**
 * Format a moment in the viewer's zone and append the course time when the zones
 * differ: «8 ноября, 18:00 (19:00 МСК)».
 */
export function formatMomentForViewer(
  instant: Date | string,
  options: Intl.DateTimeFormatOptions,
  courseTimeZone: string = DEFAULT_COURSE_TIME_ZONE,
  viewerTimeZone: string = browserTimeZone(),
  locale: Locale = currentLocale(),
): string {
  const date = typeof instant === 'string' ? new Date(instant) : instant
  if (Number.isNaN(date.getTime())) return ''
  const own = dateTimeFormat(locale, { ...options, timeZone: viewerTimeZone }).format(date)
  const hint = courseZoneHint(date, courseTimeZone, viewerTimeZone, locale)
  return hint ? `${own} (${hint})` : own
}
