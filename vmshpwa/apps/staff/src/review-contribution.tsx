import { plural, t } from '@lingui/core/macro'
import { Plural, Trans } from '@lingui/react/macro'
import { useEffect, useMemo, useRef, useState } from 'react'
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createReviewContributionClient,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  createBrowserStorageNamespace,
  type ReviewContribution as Contribution,
  type ReviewContributionQuery,
} from '@vmsh/contracts'
import { formatNumber } from '@vmsh/i18n'
import { Button, Label, Progress, toast } from '@vmsh/ui'

/** docs/review-contribution.md; design-system/05-pages-and-flows.md, Staff. */
export function ReviewContribution(props: ReviewContributionQuery) {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const queryClient = useQueryClient()
  const namespace = createBrowserStorageNamespace(auth.client.runtime)
  const identity = JSON.stringify(props)
  const [selection, setSelection] = useState<{
    identity: string
    query: ReviewContributionQuery
  } | null>(null)
  const filters = selection?.identity === identity ? selection.query : props
  const rootKey = useMemo(
    () => [namespace, principal.accountId, 'review-contribution'],
    [namespace, principal.accountId],
  )
  const queryKey = useMemo(() => [...rootKey, filters], [rootKey, filters])
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      createReviewContributionClient(auth.client.runtime, {
        refreshSession: () => auth.refresh(),
      })(filters, signal),
    staleTime: 15_000,
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    meta: { realtimeResources: ['review-queue', 'oral-results'] },
  })
  const announced = useRef(new Set<string>())
  useEffect(() => {
    const refresh = () => {
      const before = queryClient.getQueryData<Contribution>(queryKey)
      // Do not await this from a save: the next student's work must stay immediate.
      void queryClient.invalidateQueries({ queryKey: rootKey }).then(() => {
        const after = queryClient.getQueryData<Contribution>(queryKey)
        if (!before || !after) return
        const period = after.lesson
        const threshold = period?.milestone.reached
          .slice()
          .reverse()
          .find(
            (n) =>
              before.lesson !== null &&
              period.number === before.lesson.number &&
              period.courseId === before.lesson.courseId &&
              n > before.lesson.counts.total,
          )
        const lifetime = after.milestone.reached
          .slice()
          .reverse()
          .find((n) => n > before.allTime.total)
        const weekMark = after.weekly.milestone.reached
          .slice()
          .reverse()
          .find((n) => n > before.weekly.best)
        const dayMark = after.daily.milestone.reached
          .slice()
          .reverse()
          .find((n) => n > before.daily.best)
        const key = JSON.stringify([queryKey, threshold, lifetime, weekMark, dayMark])
        if ((!threshold && !lifetime && !weekMark && !dayMark) || announced.current.has(key)) return
        announced.current.add(key)
        const thresholdText = formatNumber(threshold ?? 0)
        const lifetimeText = formatNumber(lifetime ?? 0)
        if (threshold === 1)
          toast.info(t`Первая проверка за занятие. Спасибо, что помогаете ребятам разобраться.`)
        else if (threshold === 10) toast.info(t`10 проверок за занятие. Спасибо за ваш вклад.`)
        else if (threshold) toast.info(t`${thresholdText} проверок за занятие`)
        else if (lifetime === 1) toast.info(t`Первая проверка в PWA. Спасибо за помощь ученикам.`)
        else if (lifetime)
          toast.info(t`${lifetimeText} проверок в PWA. Спасибо за помощь ученикам.`)
        else if (weekMark)
          toast.info(
            plural(weekMark, {
              one: '# неделя подряд с проверками',
              few: '# недели подряд с проверками',
              many: '# недель подряд с проверками',
              other: '# недели подряд с проверками',
            }),
          )
        else if (dayMark)
          toast.info(
            plural(dayMark, {
              one: '# день подряд с проверками',
              few: '# дня подряд с проверками',
              many: '# дней подряд с проверками',
              other: '# дня подряд с проверками',
            }),
          )
      })
    }
    window.addEventListener('review-completed', refresh)
    window.addEventListener('review-contribution-saved', refresh)
    return () => {
      window.removeEventListener('review-completed', refresh)
      window.removeEventListener('review-contribution-saved', refresh)
    }
  }, [queryClient, queryKey, rootKey])
  return (
    <ReviewContributionView
      data={query.data}
      failed={query.isError || query.fetchStatus === 'paused'}
      updating={query.isPlaceholderData}
      onRetry={() => void query.refetch()}
      onSelect={(query) => setSelection({ identity, query })}
    />
  )
}

function Counts({ value }: { value: Contribution['allTime'] }) {
  return (
    <>
      <Plural
        value={value.total}
        one="# проверка"
        few="# проверки"
        many="# проверок"
        other="# проверки"
      />
      {' · '}
      <Plural value={value.plus} one="# плюс" few="# плюса" many="# плюсов" other="# плюса" />
    </>
  )
}

function Milestone({ label, value }: { label: string; value: Contribution['milestone'] }) {
  const completed = formatNumber(value.value)
  const target = formatNumber(value.next)
  return (
    <div className="space-y-1">
      <p className="text-small font-medium">{label}</p>
      <Progress className="h-2" aria-label={label} value={value.value} max={value.next} />
      <p className="font-num text-small text-muted-foreground">
        <Trans>
          {completed} из {target} проверок
        </Trans>
      </p>
      {value.reached.length > 0 && (
        <p className="text-caption text-muted-foreground">
          <Trans>Достигнутые отметки:</Trans>{' '}
          {value.reached.map((n) => formatNumber(n)).join(' · ')}
        </p>
      )}
    </div>
  )
}

function Streak({ weekly, value }: { weekly?: boolean; value: Contribution['daily'] }) {
  const nextMark = value.milestone.next
  return (
    <div className="space-y-1">
      <p className="font-medium">{weekly ? t`Недельный ритм` : t`Дневной ритм`}</p>
      <p className="text-small">
        {value.current > 0 &&
          (weekly ? (
            <Plural
              value={value.current}
              one="# неделя подряд"
              few="# недели подряд"
              many="# недель подряд"
              other="# недели подряд"
            />
          ) : (
            <Plural
              value={value.current}
              one="# день подряд"
              few="# дня подряд"
              many="# дней подряд"
              other="# дня подряд"
            />
          ))}
        {value.current > 0 ? ' · ' : null}
        <Trans>Личный рекорд:</Trans> {formatNumber(value.best)}
      </p>
      <p className="text-caption text-muted-foreground">
        {weekly ? t`Минимум 3 проверки в неделю · с понедельника` : t`Минимум 3 проверки в день`}
        {' · '}
        {weekly ? t`На этой неделе:` : t`Сегодня:`} {formatNumber(value.periodCount)}
      </p>
      <Progress
        className="h-2"
        aria-label={weekly ? t`Недельный рекорд` : t`Дневной рекорд`}
        value={value.best}
        max={value.milestone.next}
      />
      <p className="text-caption text-muted-foreground">
        {weekly ? (
          <Plural
            value={nextMark}
            one="Следующая отметка: # неделя"
            few="Следующая отметка: # недели"
            many="Следующая отметка: # недель"
            other="Следующая отметка: # недели"
          />
        ) : (
          <Plural
            value={nextMark}
            one="Следующая отметка: # день"
            few="Следующая отметка: # дня"
            many="Следующая отметка: # дней"
            other="Следующая отметка: # дня"
          />
        )}
      </p>
      {value.milestone.reached.length > 0 && (
        <p className="text-caption text-muted-foreground">
          <Trans>Достигнутые отметки:</Trans> {value.milestone.reached.join(' · ')}
        </p>
      )}
    </div>
  )
}

export function ReviewContributionView({
  data,
  failed = false,
  updating = false,
  onRetry,
  onSelect,
}: {
  data?: Contribution | undefined
  failed?: boolean
  updating?: boolean
  onRetry: () => void
  onSelect: (query: ReviewContributionQuery) => void
}) {
  if (!data)
    return failed ? (
      <div className="flex flex-wrap items-center gap-2 text-small">
        <span>
          <Trans>Ваш вклад · Не удалось загрузить показатели</Trans>
        </span>
        <Button variant="ghost" size="sm" onClick={onRetry}>
          <Trans>Повторить</Trans>
        </Button>
      </div>
    ) : null
  if (data.allTime.total === 0) return null
  const period = data.lesson
  const course = data.courses.find((c) => c.id === period?.courseId)
  const lessonNumber = period?.number ?? 0
  const courseName = course?.name ?? ''
  return (
    <details className="min-w-0 rounded-md border border-border bg-surface px-3 py-1 text-small">
      <summary className="min-h-8 cursor-pointer rounded py-1 focus-visible:outline-2 focus-visible:outline-ring">
        <span className="font-medium">
          <Trans>Ваш вклад</Trans>
        </span>
        <span className="ml-2 font-num">
          <Trans>За всё время:</Trans> {formatNumber(data.allTime.total)}
        </span>
        {period && (
          <span className="block font-num sm:ml-3 sm:inline">
            <Trans>Занятие {lessonNumber}</Trans>
            {': '}
            <Counts value={period.counts} />
          </span>
        )}
      </summary>
      <div className="space-y-4 border-t border-border py-3" aria-busy={updating}>
        {updating && (
          <p role="status" className="text-caption text-muted-foreground">
            <Trans>Обновляем показатели…</Trans>
          </p>
        )}
        {failed && (
          <div className="flex flex-wrap items-center gap-2" role="status">
            <Trans>Не удалось обновить показатели</Trans>
            <Button variant="ghost" size="sm" onClick={onRetry}>
              <Trans>Повторить</Trans>
            </Button>
          </div>
        )}
        <p className="text-caption text-muted-foreground">
          <Trans>Письменные и устные проверки через PWA. Плюсы включают «+» и «+.».</Trans>
        </p>
        <div className="flex flex-wrap gap-3">
          <Label className="grid min-w-0 gap-1">
            <Trans>Курс статистики</Trans>
            <select
              className="min-h-8 max-w-full rounded border border-input bg-background px-2"
              value={course?.id ?? ''}
              onChange={(event) =>
                onSelect(event.target.value ? { course: event.target.value } : {})
              }
            >
              <option value="">{t`Выберите курс`}</option>
              {data.courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </Label>
          {course && (
            <Label className="grid gap-1">
              <Trans>Занятие статистики</Trans>
              <select
                className="min-h-8 rounded border border-input bg-background px-2"
                value={period?.number ?? ''}
                onChange={(event) =>
                  onSelect({ course: course.id, lesson: Number(event.target.value) })
                }
              >
                {course.lessons.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </Label>
          )}
        </div>
        {!period && (
          <p>
            <Trans>Выберите курс для статистики занятия.</Trans>
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <ContributionTotals label={t`За всё время в PWA`} value={data.allTime} />
          {period && (
            <ContributionTotals
              label={t`Занятие ${lessonNumber} · ${courseName}`}
              value={period.counts}
            />
          )}
          <Milestone label={t`Ваш общий вклад`} value={data.milestone} />
          {period && <Milestone label={t`Ваш вклад за занятие`} value={period.milestone} />}
          <Streak value={data.daily} />
          <Streak weekly value={data.weekly} />
        </div>
        <p className="text-caption text-muted-foreground">
          <Trans>
            Дни и недели считаются по московскому времени. После перерыва личный рекорд сохраняется.
          </Trans>
        </p>
      </div>
    </details>
  )
}

function ContributionTotals({ label, value }: { label: string; value: Contribution['allTime'] }) {
  return (
    <div className="space-y-1">
      <h3 className="font-medium">{label}</h3>
      <p className="font-num">
        <Counts value={value} />
      </p>
      <dl className="text-caption text-muted-foreground">
        {(
          [
            ['written', t`Письменно`],
            ['school', t`Очно`],
            ['zoom', t`Zoom`],
          ] as const
        ).map(([kind, name]) => (
          <div key={kind} className="flex flex-wrap gap-x-2">
            <dt>{name}</dt>
            <dd>
              <Counts value={{ ...value, ...value.byKind[kind] }} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
