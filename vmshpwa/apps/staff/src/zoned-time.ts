import { browserTimeZone, convertWallTime, instantToWallTime, wallTimeToInstant } from '@vmsh/i18n'

/*
 * Staff type one-off moments in their own browser zone; the server stores lesson
 * times as wall time in the course zone (vmshpwa/dev/ui-audit-20261104/BACKLOG.md,
 * «Часовые пояса»). Shared helpers live in packages/i18n/src/time-zones.ts.
 */

/** Browser wall time → course wall time, the shape the lesson APIs accept. */
export function toCourseWallTime(browserWall: string, courseTimeZone: string): string {
  return convertWallTime(browserWall, browserTimeZone(), courseTimeZone)
}

/** Course wall time from the API → browser wall time for an input. */
export function fromCourseWallTime(courseWall: string, courseTimeZone: string): string {
  return convertWallTime(courseWall, courseTimeZone, browserTimeZone())
}

/** Instant from the API → browser wall time for an input. */
export function toBrowserWallTime(instant: string | null | undefined): string {
  return instant ? instantToWallTime(instant, browserTimeZone()) : ''
}

/** Browser wall time from an input → ISO instant. */
export function browserWallTimeToIso(browserWall: string): string {
  return wallTimeToInstant(browserWall, browserTimeZone())?.toISOString() ?? ''
}

export function browserNowWallTime(): string {
  return instantToWallTime(new Date(), browserTimeZone())
}
