import { Send } from 'lucide-react'
import type { FormEvent, KeyboardEvent } from 'react'

import { Alert, AlertContent, AlertDescription, Button, Textarea, cn } from '@vmsh/ui'

/**
 * Text-only private dialogue composer for Phase 6. Persistence and submission
 * remain application concerns; this component makes the true saved/failed
 * state visible and never implies that an unsaved browser value is durable.
 */
export interface SupportComposerProps {
  value: string
  onValueChange: (value: string) => void
  onSubmit: () => void
  busy?: boolean
  disabled?: boolean
  density?: 'comfortable' | 'compact'
  saveState?: 'idle' | 'saved' | 'unavailable'
  error?: string | null
  submitLabel?: string
  className?: string
}

export function SupportComposer({
  value,
  onValueChange,
  onSubmit,
  busy = false,
  disabled = false,
  density = 'comfortable',
  saveState = 'idle',
  error,
  submitLabel = 'Отправить',
  className,
}: SupportComposerProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!busy && !disabled && value.trim()) onSubmit()
  }
  const submitFromKeyboard = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      if (!busy && !disabled && value.trim()) onSubmit()
    }
  }

  return (
    <form className={cn('space-y-2', className)} onSubmit={submit}>
      <Textarea
        aria-label="Сообщение"
        disabled={disabled || busy}
        id="support-message"
        maxLength={100_000}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={submitFromKeyboard}
        placeholder="Опишите, что именно осталось непонятно…"
        rows={density === 'compact' ? 3 : 5}
        value={value}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        {saveState === 'saved' ? (
          <p className="text-caption text-muted-foreground" role="status">
            Черновик сохранён на этом устройстве.
          </p>
        ) : saveState === 'unavailable' ? (
          <p className="text-caption text-danger" role="status">
            Черновик не сохраняется. Не закрывайте страницу до отправки.
          </p>
        ) : (
          <span />
        )}
        <Button
          disabled={disabled || busy || !value.trim()}
          size="sm"
          title={`${submitLabel} (Ctrl/Cmd+Enter)`}
          type="submit"
        >
          <Send aria-hidden="true" />
          {busy ? 'Отправляем…' : submitLabel}
        </Button>
      </div>
      {error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertDescription>{error}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
    </form>
  )
}
