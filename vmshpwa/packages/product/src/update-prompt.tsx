import { Trans } from '@lingui/react/macro'
import { RefreshCw } from 'lucide-react'

import { Alert, AlertContent, AlertDescription, AlertTitle, Button } from '@vmsh/ui'

/*
 * New version available. Updating must never discard a draft or unsent text —
 * that promise is stated plainly, and «Позже» is always available.
 */
export interface UpdatePromptProps {
  onUpdate?: () => void
  onDismiss?: () => void
  className?: string
}

export function UpdatePrompt({ onUpdate, onDismiss, className }: UpdatePromptProps) {
  return (
    <Alert className={className} tone="info">
      <RefreshCw aria-hidden="true" />
      <AlertContent>
        <AlertTitle>
          <Trans>Доступно обновление</Trans>
        </AlertTitle>
        <AlertDescription>
          <Trans>Обновимся за секунду. Черновик и несохранённый текст останутся на месте.</Trans>
        </AlertDescription>
        <div className="mt-2 flex gap-2">
          <Button onClick={onUpdate} size="sm">
            <Trans>Обновить</Trans>
          </Button>
          <Button onClick={onDismiss} size="sm" variant="ghost">
            <Trans>Позже</Trans>
          </Button>
        </div>
      </AlertContent>
    </Alert>
  )
}
