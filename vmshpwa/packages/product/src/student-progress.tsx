import { Flame, Sparkles } from 'lucide-react'

import { cn } from '@vmsh/ui'

/*
 * Personal progress, words first («3 задачи зачтено»). Calm early achievements
 * and a streak measured only against one's own history — no leaderboard, no
 * percentile, no red «failures». Student and Family never receive a group
 * distribution in this component; aggregate charts belong to Staff contexts.
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
  empty?: boolean
  className?: string
}

export function StudentProgress({
  solvedCount,
  attemptedCount,
  streakDays,
  achievements = [],
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
        Пока пусто. Когда вы начнёте решать задачи, здесь появится ваш прогресс — без рейтингов и
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
          из <span className="font-num">{attemptedCount}</span>, над которыми вы работали
        </p>
      ) : null}

      {streakDays && streakDays > 1 ? (
        <p className="inline-flex items-center gap-1.5 text-small text-foreground">
          <Flame aria-hidden="true" className="size-4 text-status-warning" />
          {streakDays} {plural(streakDays, 'день', 'дня', 'дней')} подряд с решениями — ваш личный
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
    </div>
  )
}
