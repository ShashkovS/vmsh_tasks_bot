import { Trans } from '@lingui/react/macro'
import {
  browserTimeZone,
  courseZoneHint,
  timeZoneShortName,
  wallTimeToInstant,
  zonesDifferAt,
} from '@vmsh/i18n'

/* Hints for Staff time inputs; conversions live in zoned-time.ts
 * (vmshpwa/dev/ui-audit-20261104/BACKLOG.md, «Часовые пояса»). */

/** «= 19:00 МСК» under an input when the browser zone differs from the course zone. */
export function CourseTimeHint({ wall, courseTimeZone }: { wall: string; courseTimeZone: string }) {
  const instant = wall ? wallTimeToInstant(wall, browserTimeZone()) : null
  const hint = instant ? courseZoneHint(instant, courseTimeZone) : null
  if (!hint) return null
  return <span className="text-caption text-muted-foreground">= {hint}</span>
}

/** One line telling which zone the inputs of a form use. */
export function ViewerZoneNote({ courseTimeZone }: { courseTimeZone: string }) {
  const viewer = browserTimeZone()
  const now = new Date()
  const own = timeZoneShortName(viewer, now)
  if (!zonesDifferAt(now, viewer, courseTimeZone)) {
    return <Trans>Время {own}.</Trans>
  }
  const course = timeZoneShortName(courseTimeZone, now)
  return (
    <Trans>
      Время указывается по вашему часовому поясу ({own}); рядом показано время курса ({course}).
    </Trans>
  )
}
