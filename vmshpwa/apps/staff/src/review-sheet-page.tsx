import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import {
  createReviewQueueClient,
  createWrittenMaterialReassignmentClient,
  PageLayout,
  PageStatePanel,
  useAuthentication,
  useAuthenticatedPrincipal,
} from '@vmsh/app-shell'
import { SemanticMathDocument } from '@vmsh/content'
import {
  createBrowserStorageNamespace,
  type ReviewSheetSearch,
  type ReviewSheetCollection,
} from '@vmsh/contracts'
import { Button, Label } from '@vmsh/ui'
import { describeReviewError } from './review-errors'
import { ReviewSheetCard } from './review-sheet-card'

/** docs/review-sheet.md; design-system/05-pages-and-flows.md § Written review. */
export function StaffReviewSheetPage({
  search,
  onSearchChange,
}: {
  search: ReviewSheetSearch
  onSearchChange: (search: ReviewSheetSearch) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const runtime = authentication.client.runtime
  const namespace = createBrowserStorageNamespace(runtime)
  const [client] = useState(() =>
    createReviewQueueClient(runtime, { refreshSession: () => authentication.refresh() }),
  )
  const [mediaClient] = useState(() =>
    createWrittenMaterialReassignmentClient(runtime, {
      refreshSession: () => authentication.refresh(),
    }),
  )
  const [opened, setOpened] = useState(Boolean(search.lesson || search.problem))
  const [active, setActive] = useState<string | null>(null)
  const [openedCollection, setOpenedCollection] = useState<{
    identity: string
    data: ReviewSheetCollection
  } | null>(null)
  const identity = JSON.stringify([namespace, principal.accountId, search])
  const key = [namespace, principal.accountId, 'review-sheet']
  const options = useQuery({
    meta: { realtimeResources: ['review-queue'] },
    queryKey: [...key, 'options'],
    queryFn: ({ signal }) => client.sheetOptions({ signal }),
  })
  const collection = useQuery({
    queryKey: [...key, 'collection', search],
    queryFn: ({ signal }) => client.sheet(search, { signal }),
    enabled: Boolean(search.lesson || search.problem),
    refetchOnWindowFocus: false,
    meta: { realtimeResources: [] },
  })
  const lesson = search.lesson ?? collection.data?.lessonId ?? ''
  const taskSearch = { lesson: lesson || undefined, mode: search.mode }
  const tasks = useQuery({
    queryKey: [...key, 'collection', taskSearch],
    queryFn: ({ signal }) => client.sheet(taskSearch, { signal }),
    enabled: Boolean(lesson),
    refetchOnWindowFocus: false,
    meta: { realtimeResources: [] },
  })
  const choose = (next: ReviewSheetSearch, close: boolean) => {
    if (close) setOpened(false)
    setActive(null)
    onSearchChange(next)
  }
  // docs/review-sheet.md: live queue updates must not remove drafts or cards.
  if (opened && collection.data && openedCollection?.identity !== identity)
    setOpenedCollection({ identity, data: collection.data })
  const data =
    opened && openedCollection?.identity === identity ? openedCollection.data : collection.data
  const tooLarge = data && !search.problem && !data.canOpenLesson
  return (
    <PageLayout title={t`Проверка простынёй`} eyebrow={t`Письменные работы`} width="wide">
      <div className="space-y-4">
        <p className="text-small text-muted-foreground">
          <Trans>
            Работы открываются без блокировки. Договоритесь с коллегами, какие работы вы проверяете.
          </Trans>
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Label className="grid gap-1">
            <Trans>Занятие</Trans>
            <select
              className="min-h-10 max-w-full rounded border border-input bg-surface px-3"
              value={lesson}
              onChange={(event) =>
                choose({ lesson: event.target.value || undefined, mode: search.mode }, true)
              }
            >
              <option value="">{t`Выберите занятие`}</option>
              {options.data?.lessons.map((item) => (
                <option key={item.lessonId} value={item.lessonId}>
                  {item.label}
                </option>
              ))}
            </select>
          </Label>
          <Label className="grid gap-1">
            <Trans>Задача</Trans>
            <select
              className="min-h-10 max-w-full rounded border border-input bg-surface px-3"
              value={search.problem ? (collection.data?.tasks[0]?.problemId ?? search.problem) : ''}
              disabled={!lesson}
              onChange={(event) =>
                choose(
                  { lesson, problem: event.target.value || undefined, mode: search.mode },
                  true,
                )
              }
            >
              <option value="">{t`Всё занятие`}</option>
              {tasks.data?.tasks.map((item) => (
                <option key={item.problemId} value={item.problemId}>
                  {item.label} · {item.count}
                </option>
              ))}
            </select>
          </Label>
          <div className="flex gap-1" role="group" aria-label={t`Какие работы показать`}>
            <Button
              variant={search.mode === 'pending' ? 'default' : 'outline'}
              aria-pressed={search.mode === 'pending'}
              onClick={() => choose({ ...search, mode: 'pending' }, false)}
            >
              <Trans>Ожидающие</Trans>
            </Button>
            <Button
              variant={search.mode === 'all' ? 'default' : 'outline'}
              aria-pressed={search.mode === 'all'}
              onClick={() => choose({ ...search, mode: 'all' }, false)}
            >
              <Trans>Все</Trans>
            </Button>
          </div>
          <Button
            disabled={
              !(search.lesson || search.problem) || collection.isPending || Boolean(tooLarge)
            }
            onClick={async () => {
              setOpened(true)
              const result = await collection.refetch()
              if (!result.error && result.data) setOpenedCollection({ identity, data: result.data })
            }}
          >
            <Trans>Показать все решения</Trans>
          </Button>
        </div>
        {options.isPending && (
          <p role="status">
            <Trans>Загружаем занятия…</Trans>
          </p>
        )}
        {options.error && (
          <PageStatePanel
            state="error"
            description={describeReviewError(options.error)}
            actionLabel={t`Повторить`}
            onAction={() => void options.refetch()}
          />
        )}
        {options.data?.lessons.length === 0 && (
          <PageStatePanel state="empty" title={t`Нет доступных занятий`} />
        )}
        {(search.lesson || search.problem) && collection.isPending && (
          <PageStatePanel state="loading" />
        )}
        {collection.error && (
          <PageStatePanel
            state="error"
            description={describeReviewError(collection.error)}
            actionLabel={t`Повторить`}
            onAction={() => void collection.refetch()}
          />
        )}
        {tooLarge && (
          <section
            className="space-y-3 rounded border border-border p-4"
            aria-label={t`Выберите задачу`}
          >
            <p role="status">
              <Trans>
                В этом режиме у занятия {data.total} работ. Простыня занятия доступна до 300
                включительно. Выберите задачу.
              </Trans>
            </p>
            <div className="flex flex-wrap gap-2">
              {data.tasks.map((task) => (
                <Button
                  key={task.problemId}
                  variant="outline"
                  onClick={() => {
                    setOpened(true)
                    onSearchChange({ lesson, problem: task.problemId, mode: search.mode })
                  }}
                >
                  {task.label} · {task.count}
                </Button>
              ))}
            </div>
          </section>
        )}
        {opened &&
          data &&
          (!collection.error || openedCollection?.identity === identity) &&
          !tooLarge && (
            <div className="space-y-8">
              {!data.tasks.some((task) => task.cases.length) && (
                <PageStatePanel state="empty" title={t`В выбранном режиме работ нет`} />
              )}
              {data.tasks.map((task) => {
                const conditions = new Set<string>()
                return (
                  <section key={task.problemId} className="space-y-4" aria-label={task.label}>
                    <h2 className="text-heading font-semibold">{task.label}</h2>
                    <div className="space-y-3 rounded border border-border bg-surface p-4">
                      {task.parts.map((part) => {
                        const signature = part.condition
                          ? JSON.stringify(part.condition)
                          : part.problemId
                        if (conditions.has(signature)) return null
                        conditions.add(signature)
                        return (
                          <div key={part.problemId}>
                            {part.condition ? (
                              <SemanticMathDocument document={part.condition} />
                            ) : (
                              <>
                                <h3 className="font-semibold">{part.label}</h3>
                                <p className="whitespace-pre-wrap">
                                  {part.statement || t`Условие пока недоступно.`}
                                </p>
                              </>
                            )}
                          </div>
                        )
                      })}
                    </div>
                    {task.cases.map((item) => (
                      <ReviewSheetCard
                        key={item.caseId}
                        item={item}
                        client={client}
                        mediaClient={mediaClient}
                        accountId={principal.accountId}
                        namespace={namespace}
                        active={active === item.caseId}
                        onActivate={() => setActive(item.caseId)}
                        onDeactivate={() =>
                          setActive((current) => (current === item.caseId ? null : current))
                        }
                      />
                    ))}
                  </section>
                )
              })}
            </div>
          )}
      </div>
    </PageLayout>
  )
}
