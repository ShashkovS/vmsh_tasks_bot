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
  scannedAttempts: number
  updatedAttempts: number
  unchangedAttempts: number
  verdictChanges: number
  becameCorrect: number
  becameWrong: number
  formatChanges: number
  invalidFormat: number
  pendingConfiguration: number
  checkerFailed: number
  messageChanges: number
}

export interface TestAttemptRecheckPanelProps {
  pendingAttempts?: number
  studentCount?: number
  updatesRequired?: number
  verdictChanges?: number
  becameCorrect?: number
  becameWrong?: number
  formatChanges?: number
  invalidFormat?: number
  pendingConfiguration?: number
  checkerFailed?: number
  messageChanges?: number
  problem?: { displayNumber: string; title: string; correctAnswer: string | null }
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
 * Admin-only current-state repair control. It never exposes answer/checker
 * internals and always identifies the published configuration being applied. See
 * `dev/development-plan/08-phase-4-test-submissions.md`.
 */
export function TestAttemptRecheckPanel({
  pendingAttempts = 0,
  studentCount = 0,
  updatesRequired = 0,
  verdictChanges = 0,
  becameCorrect = 0,
  becameWrong = 0,
  formatChanges = 0,
  invalidFormat = 0,
  pendingConfiguration = 0,
  checkerFailed = 0,
  messageChanges = 0,
  problem,
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
      <Card aria-label="Загрузка тестовых ответов" className={className} role="status">
        <CardContent className="space-y-3 pt-5">
          <Skeleton className="h-5 w-52" />
          <Skeleton className="h-10 w-full" />
          <span className="sr-only">Загружаем сохранённые тестовые ответы</span>
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
              Перепроверка тестовых ответов
            </h2>
            <p className="mt-1 max-w-2xl text-caption leading-5 text-muted-foreground">
              Все сохранённые ответы этой задачи будут оценены по текущей конфигурации. Исходные
              посылки останутся неизменными, а прежний вердикт может измениться.
            </p>
          </div>
          <Badge variant={pendingAttempts > 0 ? 'warning' : 'neutral'}>
            Ответов: {pendingAttempts}
          </Badge>
        </div>

        {problem ? (
          <div className="rounded-md border border-border bg-surface-sunken p-3 text-small">
            <p className="font-semibold">
              Задача {problem.displayNumber}. {problem.title ? `«${problem.title}»` : ''}
            </p>
            <p className="mt-1 text-muted-foreground">
              Текущий правильный ответ: {problem.correctAnswer ?? 'не настроен'}
            </p>
          </div>
        ) : null}

        {pendingAttempts > 0 ? (
          <dl className="grid gap-2 text-small sm:grid-cols-2 lg:grid-cols-3">
            <Impact label="Школьников" value={studentCount} />
            <Impact label="Будет обновлено" value={updatesRequired} />
            <Impact label="Вердиктов изменится" value={verdictChanges} />
            <Impact label="− → +" value={becameCorrect} />
            <Impact label="+ → −" value={becameWrong} />
            <Impact label="Переходов формата" value={formatChanges} />
            <Impact label="Ошибок формата после проверки" value={invalidFormat} />
            <Impact label="Ожидают настройки" value={pendingConfiguration} />
            <Impact label="Ошибок checker-а" value={checkerFailed} />
            <Impact label="Реплик изменится" value={messageChanges} />
          </dl>
        ) : null}

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
              {applying
                ? 'Перепроверяем…'
                : `Перепроверить все ${formatAttemptCount(pendingAttempts)}`}
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-small text-status-success">
              <CheckCircle2 aria-hidden="true" className="size-4" />
              Нет сохранённых ответов
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
            Проверено {result.scannedAttempts}, обновлено {result.updatedAttempts}
          </AlertTitle>
          <AlertDescription>
            Без изменений: {result.unchangedAttempts} · верных: {result.correct} · неверных:{' '}
            {result.wrong} · вердиктов изменено: {result.verdictChanges} · реплик изменено:{' '}
            {result.messageChanges} · − → +: {result.becameCorrect} · + → −: {result.becameWrong}
            {result.formatChanges > 0 ? ` · переходов формата: ${result.formatChanges}` : ''}
            {result.invalidFormat > 0 ? ` · ошибок формата: ${result.invalidFormat}` : ''}
            {result.pendingConfiguration > 0
              ? ` · ожидают настройки: ${result.pendingConfiguration}`
              : ''}
            {result.checkerFailed > 0 ? ` · ошибок checker-а: ${result.checkerFailed}` : ''}
            {result.skippedConcurrent > 0
              ? ` · уже обработаны параллельно: ${result.skippedConcurrent}`
              : ''}
          </AlertDescription>
        </AlertContent>
      </Alert>
    </div>
  )
}

function Impact({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md border border-border px-3 py-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-num font-semibold">{value}</dd>
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
