import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { LiveMarkingClient } from '@vmsh/app-shell'
import type { LiveBoard, LiveContext } from '@vmsh/contracts'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@vmsh/ui'

const MathematicalDocument = lazy(() =>
  import('@vmsh/content').then((m) => ({ default: m.SemanticMathDocument })),
)

// live-marking.md: opening a condition is a read, independent of the mark/outbox.
export function LiveConditionDialog({
  client,
  accountId,
  context,
  problem,
  onClose,
}: {
  client: LiveMarkingClient
  accountId: string
  context: LiveContext
  problem: LiveBoard['problems'][number]
  onClose: () => void
}) {
  const condition = useQuery({
    queryKey: ['live-condition', accountId, context, problem.problemId],
    queryFn: () => client.condition(context, problem.problemId),
  })
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        className="flex max-h-[85svh] min-h-0 flex-col gap-3 sm:max-w-2xl"
        showCloseButton={false}
      >
        <DialogHeader>
          <DialogTitle>
            <Trans>Условие задачи {problem.label}</Trans>
          </DialogTitle>
          <DialogDescription>{problem.title || t`Опубликованное условие`}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-auto overscroll-contain">
          {condition.isPending ? (
            <p role="status">
              {condition.fetchStatus === 'paused'
                ? t`Для загрузки условия подключитесь к сети.`
                : t`Загружаем условие…`}
            </p>
          ) : null}
          {condition.isError ? (
            <div role="alert">
              <p>
                <Trans>Не удалось загрузить условие.</Trans>
              </p>
              <Button variant="outline" onClick={() => void condition.refetch()}>
                <Trans>Повторить</Trans>
              </Button>
            </div>
          ) : null}
          {condition.data ? (
            condition.data.document ? (
              <Suspense
                fallback={
                  <p role="status">
                    <Trans>Загружаем условие…</Trans>
                  </p>
                }
              >
                <MathematicalDocument document={condition.data.document} />
              </Suspense>
            ) : (
              <p>
                <Trans>Условие пока недоступно.</Trans>
              </p>
            )
          ) : null}
        </div>
        <Button className="min-h-11 shrink-0" variant="outline" onClick={onClose}>
          <Trans>К оценкам</Trans>
        </Button>
      </DialogContent>
    </Dialog>
  )
}
