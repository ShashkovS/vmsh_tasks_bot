import { Flame, Sparkles } from 'lucide-react'

import { cn } from '@vmsh/ui'

import { DistributionViolin } from './progress-charts'

/*
 * Personal progress, words first («3 задачи зачтено»). Calm early achievements
 * and a streak measured only against one's own history — no leaderboard, no
 * percentile, no red «failures». The group distribution is available but never
 * pushed: it hides behind a disclosure.
 */
function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few
  return many
}

export interface StudentProgressProps {
  solvedCount: number
  attemptedCount?: number
  streakDays?: number
  achievements?: string[]
  distribution?: { values: number[] }
  empty?: boolean
  className?: string
}

export function StudentProgress({
  solvedCount,
  attemptedCount,
  streakDays,
  achievements = [],
  distribution,
  empty,
  className,
}: StudentProgressProps) {
  if (empty || (solvedCount === 0 && !attemptedCount)) {
    return (
      <div
        className={cn(
          'rounded-lg border border-dashed border-border bg-surface-subtle p-4 text-small text-muted-foreground',
          className,
        )}
      >
        Пока пусто. Как начнёшь решать задачи, здесь появится твой прогресс — без рейтингов и
        сравнений.
      </div>
    )
  }

  return (
    <div className={cn('space-y-3', className)}>
      <p className="text-title font-semibold text-foreground">
        <span className="font-num">{solvedCount}</span>{' '}
        {plural(solvedCount, 'задача зачтена', 'задачи зачтено', 'задач зачтено')}
      </p>
      {attemptedCount ? (
        <p className="text-small text-muted-foreground">
          из <span className="font-num">{attemptedCount}</span>, над которыми ты работал
        </p>
      ) : null}

      {streakDays && streakDays > 1 ? (
        <p className="inline-flex items-center gap-1.5 text-small text-foreground">
          <Flame aria-hidden="true" className="size-4 text-status-warning" />
          {streakDays} {plural(streakDays, 'день', 'дня', 'дней')} подряд с решениями — твой личный
          рекорд
        </p>
      ) : null}

      {achievements.length > 0 ? (
        <ul className="space-y-1">
          {achievements.map((achievement, index) => (
            <li className="inline-flex items-center gap-1.5 text-small text-foreground" key={index}>
              <Sparkles aria-hidden="true" className="size-4 text-chart-3" />
              {achievement}
            </li>
          ))}
        </ul>
      ) : null}

      {distribution ? (
        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-small text-muted-foreground">
            Посмотреть, как решала вся группа
          </summary>
          <div className="mt-2">
            <DistributionViolin
              caption="Сколько задач решают в группе. Тебя тут не отмечаем — это про группу целиком."
              values={distribution.values}
            />
          </div>
        </details>
      ) : null}
    </div>
  )
}
