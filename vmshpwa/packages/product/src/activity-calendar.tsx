import { cn } from '@vmsh/ui'

export interface ActivityCalendarDay {
  date: string
  problemCount: number
}

export interface ActivityCalendarProps {
  days: ActivityCalendarDay[]
  className?: string
}

function parseDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year!, month! - 1, day))
}

function dateKey(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function startOfWeek(date: Date): Date {
  const result = new Date(date)
  const day = result.getUTCDay() || 7
  result.setUTCDate(result.getUTCDate() - day + 1)
  return result
}

function endOfWeek(date: Date): Date {
  const result = startOfWeek(date)
  result.setUTCDate(result.getUTCDate() + 6)
  return result
}

function intensity(count: number): string {
  if (count === 0) return 'border-border bg-surface-sunken'
  if (count === 1) return 'border-chart-2/20 bg-chart-2/20'
  if (count <= 3) return 'border-chart-2/40 bg-chart-2/45'
  return 'border-chart-2 bg-chart-2'
}

function activityLabel(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) return `${count} задача`
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)) {
    return `${count} задачи`
  }
  return `${count} задач`
}

function daysLabel(count: number): string {
  if (count % 10 === 1 && count % 100 !== 11) return `${count} день работы`
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)) {
    return `${count} дня работы`
  }
  return `${count} дней работы`
}

/** Personal course activity required by development-plan/13-phase-9-family-and-progress.md. */
export function ActivityCalendar({ days, className }: ActivityCalendarProps) {
  if (days.length === 0) return null
  const counts = new Map(days.map((day) => [day.date, day.problemCount]))
  const sortedDates = days.map((day) => day.date).sort()
  const first = startOfWeek(parseDate(sortedDates[0]!))
  const last = endOfWeek(parseDate(sortedDates.at(-1)!))
  const calendarDays: Array<{ date: string; count: number }> = []
  for (const cursor = new Date(first); cursor <= last; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const date = dateKey(cursor)
    calendarDays.push({ date, count: counts.get(date) ?? 0 })
  }
  const total = days.reduce((sum, day) => sum + day.problemCount, 0)
  const dateFormatter = new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  })

  return (
    <figure className={cn('space-y-2', className)}>
      <figcaption className="text-small text-muted-foreground">
        {daysLabel(days.length)} · {activityLabel(total)}
      </figcaption>
      <div className="max-w-full overflow-x-auto pb-1">
        <div aria-hidden="true" className="grid w-max grid-flow-col grid-rows-7 gap-1">
          {calendarDays.map((day) => (
            <span
              className={cn('size-3 rounded-[2px] border', intensity(day.count))}
              key={day.date}
              title={`${dateFormatter.format(parseDate(day.date))}: ${activityLabel(day.count)}`}
            />
          ))}
        </div>
      </div>
      <details className="text-caption text-muted-foreground">
        <summary className="cursor-pointer">Показать по датам</summary>
        <ul className="mt-2 space-y-1">
          {days.map((day) => (
            <li key={day.date}>
              <time dateTime={day.date}>{dateFormatter.format(parseDate(day.date))}</time> ·{' '}
              {activityLabel(day.problemCount)}
            </li>
          ))}
        </ul>
      </details>
    </figure>
  )
}
