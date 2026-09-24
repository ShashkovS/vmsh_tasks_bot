import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { formatDateTime } from '@vmsh/i18n'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import type { StudentResultsClient } from '@vmsh/app-shell'
import type { StudentResultEvent, StudentResultHistory, WebContentDocument } from '@vmsh/contracts'
import { ThreadMessage, VerdictMark, writtenReviewVerdict } from '@vmsh/product'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@vmsh/ui'

const MathDocument = lazy(() =>
  import('@vmsh/content').then((m) => ({ default: m.SemanticMathDocument })),
)
const AnnotationViewer = lazy(() =>
  import('@vmsh/product').then((m) => ({ default: m.ReviewAnnotationViewer })),
)
export function ResultCondition({
  document,
  legacyText,
}: {
  document: WebContentDocument | null
  legacyText?: string | null
}) {
  return document ? (
    <Suspense
      fallback={
        <p>
          <Trans>Загружаем условие…</Trans>
        </p>
      }
    >
      <MathDocument document={document} />
    </Suspense>
  ) : legacyText ? (
    <div className="space-y-1">
      <p className="text-caption text-muted-foreground">
        <Trans>Сохранённый текст условия · версия неизвестна</Trans>
      </p>
      <p className="whitespace-pre-wrap break-words">{legacyText}</p>
    </div>
  ) : (
    <p className="text-small text-muted-foreground">
      <Trans>Архивное условие недоступно.</Trans>
    </p>
  )
}
export function ResultMark({ value, symbol }: { value: number | null; symbol: string }) {
  return value !== null && value >= 11 && value <= 17 ? (
    <VerdictMark verdict={writtenReviewVerdict(value)} />
  ) : (
    <span className="font-num text-lg font-semibold">{symbol || '·'}</span>
  )
}
const kinds: Record<StudentResultEvent['kind'], string> = {
  get entry() {
    return t`Посылка / сообщение`
  },
  get test() {
    return t`Ответ на тест`
  },
  get review() {
    return t`Проверка`
  },
  get discussion() {
    return t`Сообщение`
  },
  get result() {
    return t`Оценка`
  },
  get reaction() {
    return t`Учительская пометка`
  },
  get student_reaction() {
    return t`Реакция ученику`
  },
  get legacy_reaction() {
    return t`Реакция`
  },
  get transfer() {
    return t`Перенос материалов`
  },
  get reassignment() {
    return t`Перенос материалов`
  },
  get replacement() {
    return t`Посылка заменена`
  },
  get undo() {
    return t`Отмена изменения оценки`
  },
}
const sources: Record<string, string> = {
  get pwa() {
    return t`Приложение`
  },
  telegram: 'Telegram',
  get staff() {
    return t`Преподаватель`
  },
  get archive() {
    return t`Архив`
  },
  zoom: 'Zoom',
  get school() {
    return t`Очное занятие`
  },
  get system() {
    return t`Система`
  },
  get ai() {
    return t`ИИ`
  },
}
const checks: Record<string, string> = {
  get pending_configuration() {
    return t`Ожидает настройки проверки`
  },
  get pending() {
    return t`Ожидает проверки`
  },
  get checked() {
    return t`Проверено`
  },
  get failed() {
    return t`Ошибка проверки`
  },
}
function date(value: string) {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : formatDateTime(d)
}

function ArchiveImage({ attachment }: { attachment: StudentResultEvent['attachments'][number] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(false)
  const [missing, setMissing] = useState(!attachment.available)
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setNear(true)
          observer.disconnect()
        }
      },
      { rootMargin: '400px' },
    )
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return (
    <div ref={ref} onErrorCapture={() => setMissing(true)} className="my-2 min-h-12 max-w-xl">
      {missing ? (
        <p role="status" className="text-small text-muted-foreground">
          <Trans>Файл не сохранился или недоступен.</Trans>
        </p>
      ) : attachment.kind === 'file' ? (
        <a
          className="text-primary underline"
          href={attachment.url}
          target="_blank"
          rel="noreferrer"
        >
          <Trans>Скачать вложение</Trans>
        </a>
      ) : near ? (
        attachment.annotation ? (
          <Suspense
            fallback={
              <p>
                <Trans>Загружаем фотографию…</Trans>
              </p>
            }
          >
            <AnnotationViewer
              imageAlt={t`Решение с отметками преподавателя`}
              imageSource={attachment.url}
              manifest={attachment.annotation}
            />
          </Suspense>
        ) : (
          <a
            href={attachment.url}
            target="_blank"
            rel="noreferrer"
            aria-label={t`Открыть вложение`}
          >
            <img
              className="max-h-96 max-w-full rounded object-contain"
              src={attachment.url}
              alt={t`Вложение к посылке`}
              loading="lazy"
              onError={() => setMissing(true)}
            />
          </a>
        )
      ) : (
        <p className="text-small text-muted-foreground">
          <Trans>Фотография</Trans>
        </p>
      )}
    </div>
  )
}

// Full chronological archive (student-results.md), composed with shared feedback and annotations.
export function ResultHistory({
  client,
  student,
  problem,
  initial,
  scope,
}: {
  client: StudentResultsClient
  student: string
  problem: string
  initial?: StudentResultHistory
  scope: string
}) {
  const [revision, setRevision] = useState<string | null>(null)
  const query = useInfiniteQuery({
    queryKey: ['student-results', scope, 'history', student, problem],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => client.history(student, problem, pageParam),
    getNextPageParam: (last) => last.nextCursor ?? undefined,
    ...(initial ? { initialData: { pages: [initial], pageParams: [undefined] } } : {}),
    staleTime: 30_000,
  })
  const condition = useQuery({
    queryKey: ['student-results', scope, 'condition', student, problem, revision],
    queryFn: () => client.condition(student, problem, revision!),
    enabled: revision !== null,
  })
  const events = query.data?.pages.flatMap((p) => p.events) ?? []
  return (
    <div className="space-y-3">
      {query.isPending && (
        <p role="status">
          <Trans>Загружаем историю…</Trans>
        </p>
      )}
      {query.isError && (
        <p role="alert">
          <Trans>Не удалось загрузить историю. </Trans>
          <Button variant="outline" onClick={() => void query.refetch()}>
            <Trans>Повторить</Trans>
          </Button>
        </p>
      )}
      {!query.isPending && !query.isError && !events.length && (
        <p className="text-small text-muted-foreground">
          <Trans>Сохранённых событий нет.</Trans>
        </p>
      )}
      <ol className="space-y-2 break-words">
        {events.map((e) => (
          <ThreadMessage
            key={e.id}
            message={{
              id: e.id,
              author: {
                kind: e.authorKind,
                name: e.author ?? sources[e.source] ?? t`Архив`,
              },
              at: date(e.at),
              body: (
                <>
                  <div className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
                    <span>
                      {kinds[e.kind]} · {sources[e.source] ?? t`Архив`}
                    </span>
                    {e.internal && (
                      <span className="font-semibold">
                        <Trans>Внутренняя пометка</Trans>
                      </span>
                    )}
                    {e.action === 'deleted' && (
                      <span>
                        <Trans>Удалена</Trans>
                      </span>
                    )}
                    {e.verdict !== null && <ResultMark value={e.verdict} symbol={e.symbol} />}
                  </div>
                  {e.text && (
                    <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{e.text}</p>
                  )}
                  {e.checkStatus && (
                    <p className="text-caption text-muted-foreground">
                      {checks[e.checkStatus] ?? t`Статус проверки неизвестен`}
                    </p>
                  )}
                  {e.transfer && (
                    <p>
                      {e.transfer.mode === 'clone' ? t`Копия` : t`Перенос`}
                      <Trans>
                        : задача {e.transfer.source} → {e.transfer.target}
                      </Trans>
                    </p>
                  )}
                  {e.attachments.map((a) => (
                    <ArchiveImage key={a.id} attachment={a} />
                  ))}
                  {e.revisionId && (
                    <Button variant="ghost" size="sm" onClick={() => setRevision(e.revisionId)}>
                      <Trans>Условие на момент отправки</Trans>
                    </Button>
                  )}
                  {e.reviewId && (
                    <a
                      className="ml-2 text-small text-primary underline"
                      href={`/staff/review/history?review=${encodeURIComponent(e.reviewId)}`}
                    >
                      <Trans>Открыть проверку</Trans>
                    </a>
                  )}
                </>
              ),
            }}
          />
        ))}
      </ol>
      {query.hasNextPage && (
        <Button
          variant="outline"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          <Trans>
            Ещё 50 событий ({events.length} из {query.data?.pages[0]?.total})
          </Trans>
        </Button>
      )}
      <Dialog
        open={revision !== null}
        onOpenChange={(open) => {
          if (!open) setRevision(null)
        }}
      >
        <DialogContent className="max-h-[85svh] overflow-auto">
          <DialogHeader>
            <DialogTitle>
              <Trans>Условие при отправке</Trans>
            </DialogTitle>
            <DialogDescription>
              <Trans>Версия, связанная с этой посылкой</Trans>
            </DialogDescription>
          </DialogHeader>
          {condition.isPending ? (
            <p>
              <Trans>Загружаем…</Trans>
            </p>
          ) : condition.isError ? (
            <p role="alert">
              <Trans>Не удалось загрузить условие.</Trans>
            </p>
          ) : (
            <ResultCondition document={condition.data?.document ?? null} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
