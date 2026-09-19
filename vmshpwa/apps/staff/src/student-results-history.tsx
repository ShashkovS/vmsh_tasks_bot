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
    <Suspense fallback={<p>Загружаем условие…</p>}>
      <MathDocument document={document} />
    </Suspense>
  ) : legacyText ? (
    <div className="space-y-1">
      <p className="text-caption text-muted-foreground">
        Сохранённый текст условия · версия неизвестна
      </p>
      <p className="whitespace-pre-wrap break-words">{legacyText}</p>
    </div>
  ) : (
    <p className="text-small text-muted-foreground">Архивное условие недоступно.</p>
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
  entry: 'Посылка / сообщение',
  test: 'Ответ на тест',
  review: 'Проверка',
  discussion: 'Сообщение',
  result: 'Оценка',
  reaction: 'Учительская пометка',
  student_reaction: 'Реакция ученику',
  legacy_reaction: 'Реакция',
  transfer: 'Перенос материалов',
  reassignment: 'Перенос материалов',
  replacement: 'Посылка заменена',
  undo: 'Отмена изменения оценки',
}
const sources: Record<string, string> = {
  pwa: 'Приложение',
  telegram: 'Telegram',
  staff: 'Преподаватель',
  archive: 'Архив',
  zoom: 'Zoom',
  school: 'Очное занятие',
  system: 'Система',
  ai: 'ИИ',
}
const checks: Record<string, string> = {
  pending_configuration: 'Ожидает настройки проверки',
  pending: 'Ожидает проверки',
  checked: 'Проверено',
  failed: 'Ошибка проверки',
}
function date(value: string) {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('ru-RU')
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
          Файл не сохранился или недоступен.
        </p>
      ) : attachment.kind === 'file' ? (
        <a
          className="text-primary underline"
          href={attachment.url}
          target="_blank"
          rel="noreferrer"
        >
          Скачать вложение
        </a>
      ) : near ? (
        attachment.annotation ? (
          <Suspense fallback={<p>Загружаем фотографию…</p>}>
            <AnnotationViewer
              imageAlt="Решение с отметками преподавателя"
              imageSource={attachment.url}
              manifest={attachment.annotation}
            />
          </Suspense>
        ) : (
          <a href={attachment.url} target="_blank" rel="noreferrer" aria-label="Открыть вложение">
            <img
              className="max-h-96 max-w-full rounded object-contain"
              src={attachment.url}
              alt="Вложение к посылке"
              loading="lazy"
              onError={() => setMissing(true)}
            />
          </a>
        )
      ) : (
        <p className="text-small text-muted-foreground">Фотография</p>
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
      {query.isPending && <p role="status">Загружаем историю…</p>}
      {query.isError && (
        <p role="alert">
          Не удалось загрузить историю.{' '}
          <Button variant="outline" onClick={() => void query.refetch()}>
            Повторить
          </Button>
        </p>
      )}
      {!query.isPending && !query.isError && !events.length && (
        <p className="text-small text-muted-foreground">Сохранённых событий нет.</p>
      )}
      <ol className="space-y-2 break-words">
        {events.map((e) => (
          <ThreadMessage
            key={e.id}
            message={{
              id: e.id,
              author: {
                kind: e.authorKind,
                name: e.author ?? sources[e.source] ?? 'Архив',
              },
              at: date(e.at),
              body: (
                <>
                  <div className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
                    <span>
                      {kinds[e.kind]} · {sources[e.source] ?? 'Архив'}
                    </span>
                    {e.internal && <span className="font-semibold">Внутренняя пометка</span>}
                    {e.action === 'deleted' && <span>Удалена</span>}
                    {e.verdict !== null && <ResultMark value={e.verdict} symbol={e.symbol} />}
                  </div>
                  {e.text && (
                    <p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{e.text}</p>
                  )}
                  {e.checkStatus && (
                    <p className="text-caption text-muted-foreground">
                      {checks[e.checkStatus] ?? 'Статус проверки неизвестен'}
                    </p>
                  )}
                  {e.transfer && (
                    <p>
                      {e.transfer.mode === 'clone' ? 'Копия' : 'Перенос'}: задача{' '}
                      {e.transfer.source} → {e.transfer.target}
                    </p>
                  )}
                  {e.attachments.map((a) => (
                    <ArchiveImage key={a.id} attachment={a} />
                  ))}
                  {e.revisionId && (
                    <Button variant="ghost" size="sm" onClick={() => setRevision(e.revisionId)}>
                      Условие на момент отправки
                    </Button>
                  )}
                  {e.reviewId && (
                    <a
                      className="ml-2 text-small text-primary underline"
                      href={`/staff/review/history?review=${encodeURIComponent(e.reviewId)}`}
                    >
                      Открыть проверку
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
          Ещё 50 событий ({events.length} из {query.data?.pages[0]?.total})
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
            <DialogTitle>Условие при отправке</DialogTitle>
            <DialogDescription>Версия, связанная с этой посылкой</DialogDescription>
          </DialogHeader>
          {condition.isPending ? (
            <p>Загружаем…</p>
          ) : condition.isError ? (
            <p role="alert">Не удалось загрузить условие.</p>
          ) : (
            <ResultCondition document={condition.data?.document ?? null} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
