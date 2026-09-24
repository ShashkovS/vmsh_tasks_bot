import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { BellRing, CheckCircle2, CircleAlert, MessageCircle, RefreshCw, Send } from 'lucide-react'
import { useId, useState } from 'react'

import type {
  ClassroomDeliveryBatch,
  ClassroomDeliveryChannel,
  ClassroomDeliveryPreview,
} from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Checkbox,
  Label,
  Separator,
  cn,
} from '@vmsh/ui'

// Explicit-send flow: dev/design-system/04-product-components.md and
// dev/development-plan/11-phase-7-oral-and-classrooms.md.
export interface ClassroomDeliveryPanelProps {
  preview?: ClassroomDeliveryPreview | null
  batch?: ClassroomDeliveryBatch | null
  changedAfterSend?: boolean
  pending?: boolean
  error?: string | null
  onPreview?: () => void
  onSend?: (channels: ClassroomDeliveryChannel[]) => void
  onRetryFailed?: () => void
  className?: string
}

const deliveryCounterLabels = {
  get selected() {
    return t`выбрано`
  },
  get eligible() {
    return t`доступно`
  },
  get suppressed() {
    return t`исключено`
  },
  get queued() {
    return t`в очереди`
  },
  get attempted() {
    return t`начато`
  },
  get succeeded() {
    return t`успешно`
  },
  get failed() {
    return t`ошибок`
  },
} as const

function isPartialRecipient(
  batch: ClassroomDeliveryBatch,
  recipient: ClassroomDeliveryBatch['recipients'][number],
) {
  const states = batch.channels.map((channel) => recipient[channel].state)
  const succeeded = states.filter((state) => state === 'sent').length
  return succeeded > 0 && succeeded < states.length
}

function channelResultLabel(
  channel: ClassroomDeliveryChannel,
  state: ClassroomDeliveryBatch['recipients'][number]['pwa']['state'],
) {
  const name = channel === 'pwa' ? 'PWA' : 'Telegram'
  const stateLabel = {
    not_requested: t`не выбран`,
    queued: t`в очереди`,
    sent: t`доставлено`,
    suppressed: t`недоступно`,
    failed: t`ошибка`,
  }[state]
  return `${name}: ${stateLabel}`
}

function DeliveryReport({ batch }: { batch: ClassroomDeliveryBatch }) {
  const failed =
    batch.deliveryReport.channels.pwa.failed + batch.deliveryReport.channels.telegram.failed
  const partialRecipients = batch.recipients.filter((recipient) =>
    isPartialRecipient(batch, recipient),
  )
  return (
    <div className="space-y-3" data-testid="classroom-delivery-report">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={batch.state === 'completed_with_errors' ? 'danger' : 'success'}>
          {batch.state === 'queued'
            ? t`Рассылка выполняется`
            : batch.state === 'completed_with_errors'
              ? t`Завершено с ошибками`
              : t`Рассылка завершена`}
        </Badge>
        <span className="text-caption text-muted-foreground">
          <Trans>
            План v{batch.planVersion} · {batch.recipientCount} получателей
          </Trans>
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5" aria-label={t`Общий результат доставки`}>
        <Badge variant="success">
          <Trans>Получили хотя бы одно: {batch.deliveryReport.deliveredAny}</Trans>
        </Badge>
        <Badge variant="outline">
          <Trans>Получили всё: {batch.deliveryReport.deliveredAll}</Trans>
        </Badge>
        {batch.deliveryReport.partial ? (
          <Badge variant="warning">
            <Trans>Частично: {batch.deliveryReport.partial}</Trans>
          </Badge>
        ) : null}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {batch.channels.map((channel) => {
          const counts = batch.deliveryReport.channels[channel]
          return (
            <div className="rounded-md border border-border bg-surface-subtle p-2.5" key={channel}>
              <p className="flex items-center gap-1.5 text-small font-medium text-foreground">
                {channel === 'pwa' ? (
                  <BellRing aria-hidden="true" className="size-4" />
                ) : (
                  <MessageCircle aria-hidden="true" className="size-4" />
                )}
                {channel === 'pwa' ? 'PWA' : 'Telegram'}
              </p>
              <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 text-caption sm:grid-cols-3">
                {Object.entries(deliveryCounterLabels).map(([key, label]) => (
                  <div className="flex justify-between gap-2" key={key}>
                    <dt className="text-muted-foreground">{label}</dt>
                    <dd className="tabular-nums text-foreground">
                      {counts[key as keyof typeof counts]}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )
        })}
      </div>
      {partialRecipients.length ? (
        <details className="rounded-md border border-border bg-surface-subtle p-2.5">
          <summary className="cursor-pointer text-small font-medium text-foreground">
            <Trans>Частично доставлено ({partialRecipients.length})</Trans>
          </summary>
          <ul className="mt-2 divide-y divide-border" data-testid="partial-recipient-list">
            {partialRecipients.map((recipient) => (
              <li className="space-y-0.5 py-1.5 text-caption" key={recipient.studentPublicId}>
                <p className="font-medium text-foreground">{recipient.studentName}</p>
                <p className="text-muted-foreground">
                  <Trans>
                    {recipient.courseName} · {recipient.groupName} · аудитория{' '}
                    {recipient.classroomName}
                  </Trans>
                </p>
                <p className="text-muted-foreground">
                  {batch.channels
                    .map((channel) => channelResultLabel(channel, recipient[channel].state))
                    .join(' · ')}
                </p>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {failed ? (
        <Alert role="alert" tone="danger">
          <CircleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>
              <Trans>Не всем удалось отправить</Trans>
            </AlertTitle>
            <AlertDescription>
              <Trans>
                Повтор затронет только неуспешные пары «школьник — канал» и не продублирует уже
                доставленные сообщения.
              </Trans>
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
    </div>
  )
}

export function ClassroomDeliveryPanel({
  preview,
  batch,
  changedAfterSend = false,
  pending = false,
  error,
  onPreview,
  onSend,
  onRetryFailed,
  className,
}: ClassroomDeliveryPanelProps) {
  const pwaId = useId()
  const telegramId = useId()
  const [pwa, setPwa] = useState(true)
  const [telegram, setTelegram] = useState(true)
  const channels: ClassroomDeliveryChannel[] = [
    ...(pwa ? (['pwa'] as const) : []),
    ...(telegram ? (['telegram'] as const) : []),
  ]
  const failed = batch
    ? batch.deliveryReport.channels.pwa.failed + batch.deliveryReport.channels.telegram.failed
    : 0

  return (
    <section
      className={cn('space-y-3 rounded-lg border border-border bg-surface p-4', className)}
      data-density="staff"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-label font-semibold text-foreground">
            <Trans>Разослать аудитории</Trans>
          </h3>
          <p className="text-caption text-muted-foreground">
            <Trans>
              Отдельное действие после подтверждения плана. Черновые перестановки никому не
              отправляются.
            </Trans>
          </p>
        </div>
        {batch ? (
          <Badge variant="outline">
            <Trans>Последняя версия: v{batch.planVersion}</Trans>
          </Badge>
        ) : null}
      </header>

      {changedAfterSend ? (
        <Alert role="status" tone="warning">
          <CircleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>
              <Trans>После рассылки назначения изменились</Trans>
            </AlertTitle>
            <AlertDescription>
              <Trans>
                Новые аудитории ещё не отправлены. Подготовьте новый предпросмотр и запустите
                рассылку явно.
              </Trans>
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>
              <Trans>Рассылка не выполнена</Trans>
            </AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {batch && !changedAfterSend ? <DeliveryReport batch={batch} /> : null}

      {preview ? (
        <div className="space-y-3">
          <Separator />
          <div className="flex flex-wrap gap-1.5" aria-label={t`Сводка предпросмотра`}>
            <Badge variant="neutral">
              <Trans>Получателей: {preview.recipientCount}</Trans>
            </Badge>
            <Badge variant={preview.changedCount ? 'warning' : 'outline'}>
              <Trans>Изменились: {preview.changedCount}</Trans>
            </Badge>
            {preview.telegramUnavailableCount ? (
              <Badge variant="danger">
                <Trans>Без Telegram: {preview.telegramUnavailableCount}</Trans>
              </Badge>
            ) : null}
          </div>

          <fieldset className="space-y-2">
            <legend className="text-small font-medium text-foreground">
              <Trans>Куда отправить</Trans>
            </legend>
            <Label
              className="flex items-start gap-2 rounded-md border border-border p-2.5"
              htmlFor={pwaId}
            >
              <Checkbox
                checked={pwa}
                id={pwaId}
                onCheckedChange={(checked) => setPwa(checked === true)}
              />
              <span>
                <Trans>
                  <span className="block text-small font-medium text-foreground">PWA</span>
                  <span className="block text-caption text-muted-foreground">
                    Объявление в кабинете школьника. Родителю уведомление не отправляется.
                  </span>
                </Trans>
              </span>
            </Label>
            <Label
              className="flex items-start gap-2 rounded-md border border-border p-2.5"
              htmlFor={telegramId}
            >
              <Checkbox
                checked={telegram}
                id={telegramId}
                onCheckedChange={(checked) => setTelegram(checked === true)}
              />
              <span>
                <Trans>
                  <span className="block text-small font-medium text-foreground">Telegram</span>
                  <span className="block text-caption text-muted-foreground">
                    Личное сообщение школьнику от существующего бота.
                  </span>
                </Trans>
              </span>
            </Label>
          </fieldset>

          <details className="rounded-md border border-border bg-surface-subtle p-2.5">
            <summary className="cursor-pointer text-small font-medium text-foreground">
              <Trans>Проверить получателей ({preview.recipientCount})</Trans>
            </summary>
            <ul className="mt-2 divide-y divide-border">
              {preview.recipients.map((recipient) => (
                <li
                  className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-1.5 text-caption"
                  key={`${recipient.studentPublicId}:${recipient.coursePublicId}`}
                >
                  <span className="font-medium text-foreground">{recipient.studentName}</span>
                  <span className="text-muted-foreground">
                    {recipient.courseName} · {recipient.groupName} · {recipient.classroomName}
                    {recipient.changed ? t` · изменено` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </details>

          <Button
            disabled={pending || channels.length === 0}
            onClick={() => onSend?.(channels)}
            size="sm"
            type="button"
          >
            <Send aria-hidden="true" />
            {pending ? t`Запускаем…` : t`Разослать аудитории`}
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={pending} onClick={onPreview} size="sm" type="button" variant="outline">
            {changedAfterSend ? (
              <RefreshCw aria-hidden="true" />
            ) : batch ? (
              <CheckCircle2 aria-hidden="true" />
            ) : (
              <Send aria-hidden="true" />
            )}
            {pending ? t`Готовим…` : t`Подготовить предпросмотр`}
          </Button>
        </div>
      )}

      {failed && onRetryFailed ? (
        <Button
          disabled={pending}
          onClick={onRetryFailed}
          size="xs"
          type="button"
          variant="outline"
        >
          <RefreshCw aria-hidden="true" />
          <Trans>Повторить только ошибки</Trans>
        </Button>
      ) : null}
    </section>
  )
}
