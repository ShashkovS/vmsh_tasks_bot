import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { AlertTriangle, Lock, UserRound } from 'lucide-react'

import { Alert, AlertContent, AlertDescription, AlertTitle, Button, cn } from '@vmsh/ui'

/*
 * Review lease state. A work held by someone else stays visible with their name
 * and a disabled action. Losing the lease blocks a now-stale verdict and demands
 * a refetch before continuing.
 */
export type ReviewLockState = 'held' | 'busy' | 'lost'

export interface ReviewLockProps {
  state: ReviewLockState
  holderName?: string
  expiresInLabel?: string
  onRefetch?: () => void
  className?: string
}

export function ReviewLock({
  state,
  holderName,
  expiresInLabel,
  onRefetch,
  className,
}: ReviewLockProps) {
  if (state === 'held') {
    return (
      <p
        className={cn(
          'inline-flex items-center gap-1.5 text-caption text-muted-foreground',
          className,
        )}
        role="status"
      >
        <Lock aria-hidden="true" className="size-3.5" />
        <Trans>Работа за вами</Trans>
        {expiresInLabel ? ` · ${expiresInLabel}` : ''}
      </p>
    )
  }

  if (state === 'busy') {
    return (
      <Alert className={className} tone="neutral">
        <UserRound aria-hidden="true" />
        <AlertContent>
          <AlertTitle>
            <Trans>Проверяет</Trans> {holderName ?? t`другой преподаватель`}
          </AlertTitle>
          <AlertDescription>
            <Trans>Откроется, когда освободится или через 30 минут.</Trans>
          </AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  return (
    <Alert className={className} role="alert" tone="danger">
      <AlertTriangle aria-hidden="true" />
      <AlertContent>
        <AlertTitle>
          <Trans>Работа больше не за вами</Trans>
        </AlertTitle>
        <AlertDescription>
          <Trans>
            Аренда истекла или досталась другому. Вердикт устарел — обновите работу, прежде чем
            продолжить.
          </Trans>
        </AlertDescription>
        {onRefetch ? (
          <div className="mt-2">
            <Button onClick={onRefetch} size="sm" variant="outline">
              <Trans>Обновить работу</Trans>
            </Button>
          </div>
        ) : null}
      </AlertContent>
    </Alert>
  )
}
