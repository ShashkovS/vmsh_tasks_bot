import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { CircleHelp } from 'lucide-react'
import { useId, useState } from 'react'

import { Button, Checkbox, Label, Textarea, cn } from '@vmsh/ui'

const selectClass =
  'min-h-(--touch-target) w-full rounded-md border border-input bg-surface px-3 text-small text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40'

/* ── Broadcast composer ─────────────────────────────────────────────────── */

export interface AudiencePreset {
  id: string
  label: string
  count: number
}

export interface BroadcastPayload {
  audienceId: string
  text: string
  channels: string[]
  category: string
  quiet: boolean
}

export interface BroadcastComposerProps {
  audiencePresets: AudiencePreset[]
  categories?: { id: string; label: string }[]
  onDryRun?: (payload: BroadcastPayload) => void
  onSend?: (payload: BroadcastPayload) => void
  className?: string
}

export function BroadcastComposer({
  audiencePresets,
  categories = [
    { id: 'important', label: t`Важное` },
    { id: 'news', label: t`Новости` },
  ],
  onDryRun,
  onSend,
  className,
}: BroadcastComposerProps) {
  const audienceId = useId()
  const categoryId = useId()
  const textId = useId()
  const pwaId = useId()
  const tgId = useId()
  const quietId = useId()
  const [audience, setAudience] = useState(audiencePresets[0]?.id ?? '')
  const [text, setText] = useState('')
  const [pwa, setPwa] = useState(true)
  const [telegram, setTelegram] = useState(true)
  const [category, setCategory] = useState(categories[0]?.id ?? '')
  const [quiet, setQuiet] = useState(true)
  const [confirming, setConfirming] = useState(false)

  const count = audiencePresets.find((preset) => preset.id === audience)?.count ?? 0
  const channels = [pwa ? 'pwa' : null, telegram ? 'telegram' : null].filter(Boolean) as string[]
  const payload: BroadcastPayload = { audienceId: audience, text, channels, category, quiet }
  const canSend = text.trim() !== '' && channels.length > 0

  return (
    <div className={cn('max-w-lg space-y-4', className)}>
      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={audienceId}>
          <Trans>Кому</Trans>
        </label>
        <select
          className={selectClass}
          id={audienceId}
          onChange={(event) => setAudience(event.target.value)}
          value={audience}
        >
          {audiencePresets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.label} ({preset.count})
            </option>
          ))}
        </select>
        <p className="text-caption text-muted-foreground" role="status">
          <Trans>
            Получат: <span className="font-num font-medium text-foreground">{count}</span>
          </Trans>
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={textId}>
          <Trans>Сообщение</Trans>
        </label>
        <Textarea
          className="min-h-24"
          id={textId}
          onChange={(event) => {
            setText(event.target.value)
            setConfirming(false)
          }}
          value={text}
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-label font-medium text-foreground">
          <Trans>Куда доставить</Trans>
        </legend>
        <div className="flex flex-wrap gap-4">
          <span className="inline-flex items-center gap-2">
            <Checkbox
              checked={pwa}
              id={pwaId}
              onCheckedChange={(value) => setPwa(Boolean(value))}
            />
            <Label htmlFor={pwaId}>
              <Trans>В приложении</Trans>
            </Label>
          </span>
          <span className="inline-flex items-center gap-2">
            <Checkbox
              checked={telegram}
              id={tgId}
              onCheckedChange={(value) => setTelegram(Boolean(value))}
            />
            <Label htmlFor={tgId}>Telegram</Label>
          </span>
        </div>
      </fieldset>

      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={categoryId}>
          <Trans>Категория</Trans>
        </label>
        <select
          className={selectClass}
          id={categoryId}
          onChange={(event) => setCategory(event.target.value)}
          value={category}
        >
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>

      <span className="inline-flex items-center gap-2">
        <Checkbox
          checked={quiet}
          id={quietId}
          onCheckedChange={(value) => setQuiet(Boolean(value))}
        />
        <Label htmlFor={quietId}>
          <Trans>Уважать тихие часы</Trans>
        </Label>
      </span>

      {confirming ? (
        <div className="space-y-2 rounded-md border border-border bg-surface-subtle p-3 text-small">
          <p className="text-foreground">
            <Trans>Отправить {count} получателям?</Trans>
          </p>
          <div className="flex gap-2">
            <Button
              onClick={() => {
                onSend?.(payload)
                setConfirming(false)
              }}
              size="sm"
            >
              <Trans>Отправить</Trans>
            </Button>
            <Button onClick={() => setConfirming(false)} size="sm" variant="ghost">
              <Trans>Отмена</Trans>
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button onClick={() => onDryRun?.(payload)} size="sm" variant="outline">
            <Trans>Пробный прогон</Trans>
          </Button>
          <Button disabled={!canSend} onClick={() => setConfirming(true)} size="sm">
            <Trans>Отправить…</Trans>
          </Button>
        </div>
      )}
    </div>
  )
}

/* ── SOS / questions queue ──────────────────────────────────────────────── */

export interface SosItem {
  id: string
  studentName: string
  taskNumber?: string
  question: string
  at: string
  status: 'open' | 'answered'
}

export interface SosQueueProps {
  items: SosItem[]
  onOpen?: (id: string) => void
  className?: string
}

export function SosQueue({ items, onOpen, className }: SosQueueProps) {
  return (
    <ul className={cn('space-y-2', className)}>
      {items.map((item) => (
        <li
          className="flex items-start gap-3 rounded-md border border-border bg-surface p-3"
          key={item.id}
        >
          <CircleHelp
            aria-hidden="true"
            className={cn(
              'mt-0.5 size-5 shrink-0',
              item.status === 'open' ? 'text-status-info' : 'text-muted-foreground',
            )}
          />
          <div className="min-w-0 flex-1 space-y-0.5">
            <div className="flex flex-wrap items-center gap-x-2 text-small">
              <span className="font-medium text-foreground">{item.studentName}</span>
              {item.taskNumber ? (
                <span className="font-num text-muted-foreground">{item.taskNumber}</span>
              ) : null}
              <time className="text-caption text-muted-foreground">{item.at}</time>
            </div>
            <p className="line-clamp-2 text-small text-muted-foreground">{item.question}</p>
          </div>
          <Button onClick={() => onOpen?.(item.id)} size="xs" variant="outline">
            {item.status === 'open' ? t`Ответить` : t`Открыть`}
          </Button>
        </li>
      ))}
    </ul>
  )
}
