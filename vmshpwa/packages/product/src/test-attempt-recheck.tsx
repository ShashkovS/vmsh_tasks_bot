import { CheckCircle2, CircleAlert, RefreshCw, Wrench } from 'lucide-react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  Skeleton,
  cn,
} from '@vmsh/ui'

export interface TestAttemptRecheckResultView {
  pendingBefore: number
  checked: number
  correct: number
  wrong: number
  stillPending: number
  skippedConcurrent: number
}

export interface TestAttemptRecheckPanelProps {
  pendingAttempts?: number
  problemRevision?: {
    conditionRevisionId: string
    configVersion: number
  }
  result?: TestAttemptRecheckResultView
  loading?: boolean
  applying?: boolean
  error?: string
  onApply?: () => void
  onRetry?: () => void
  className?: string
}

/**
 * Admin-only Phase-4 recovery control for attempts accepted while a test
 * checker was missing or broken. It never exposes answer/checker internals and
 * always identifies the immutable published revision being applied. See
 * `dev/development-plan/08-phase-4-test-submissions.md`.
 */
export function TestAttemptRecheckPanel({
  pendingAttempts = 0,
  problemRevision,
  result,
  loading = false,
  applying = false,
  error,
  onApply,
  onRetry,
  className,
}: TestAttemptRecheckPanelProps) {
  if (loading) {
    return (
      <Card aria-label="Загрузка отложенных ответов" className={className} role="status">
        <CardContent className="space-y-3 pt-5">
          <Skeleton className="h-5 w-52" />
          <Skeleton className="h-10 w-full" />
          <span className="sr-only">Проверяем, есть ли отложенные ответы</span>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="space-y-4 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="flex items-center gap-2 text-small font-semibold text-foreground">
              <Wrench aria-hidden="true" className="size-4 text-muted-foreground" />
              Отложенные тестовые ответы
            </h2>
            <p className="mt-1 max-w-2xl text-caption leading-5 text-muted-foreground">
              Ответы, принятые при недоступной проверке, можно проверить после публикации
              исправленной конфигурации. Исходные посылки останутся неизменными.
            </p>
          </div>
          <Badge variant={pendingAttempts > 0 ? 'warning' : 'neutral'}>
            Ожидают: {pendingAttempts}
          </Badge>
        </div>

        {problemRevision ? (
          <p className="font-num text-caption text-muted-foreground">
            Текущая опубликованная версия: v{problemRevision.configVersion} ·{' '}
            {problemRevision.conditionRevisionId}
          </p>
        ) : null}

        {result ? <RecheckResult result={result} /> : null}

        {error ? (
          <Alert tone="danger">
            <CircleAlert aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Не удалось выполнить перепроверку</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          {pendingAttempts > 0 ? (
            <Button disabled={applying || !onApply} onClick={onApply} size="sm" type="button">
              <RefreshCw
                aria-hidden="true"
                className={applying ? 'animate-spin motion-reduce:animate-none' : undefined}
              />
              {applying ? 'Перепроверяем…' : `Перепроверить ${formatAttemptCount(pendingAttempts)}`}
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-small text-status-success">
              <CheckCircle2 aria-hidden="true" className="size-4" />
              Нет ответов, ожидающих настройки
            </span>
          )}
          {error && onRetry ? (
            <Button disabled={applying} onClick={onRetry} size="sm" type="button" variant="outline">
              Обновить данные
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

function RecheckResult({ result }: { result: TestAttemptRecheckResultView }) {
  const hasUnresolved = result.stillPending > 0 || result.skippedConcurrent > 0
  return (
    <div className="space-y-2" role="status" aria-live="polite">
      <Alert tone={hasUnresolved ? 'warning' : 'success'}>
        <AlertContent>
          <AlertTitle>
            Проверено {result.checked} из {result.pendingBefore}
          </AlertTitle>
          <AlertDescription>
            Верных: {result.correct} · неверных: {result.wrong}
            {result.stillPending > 0 ? ` · всё ещё ожидают настройки: ${result.stillPending}` : ''}
            {result.skippedConcurrent > 0
              ? ` · уже обработаны параллельно: ${result.skippedConcurrent}`
              : ''}
          </AlertDescription>
        </AlertContent>
      </Alert>
    </div>
  )
}

function formatAttemptCount(count: number): string {
  const modulo100 = count % 100
  const modulo10 = count % 10
  if (modulo100 >= 11 && modulo100 <= 14) return `${count} ответов`
  if (modulo10 === 1) return `${count} ответ`
  if (modulo10 >= 2 && modulo10 <= 4) return `${count} ответа`
  return `${count} ответов`
}
