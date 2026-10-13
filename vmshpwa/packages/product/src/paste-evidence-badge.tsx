import { useId, useState } from 'react'
import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import type { PasteEstimate } from '@vmsh/contracts'
import { Badge, Tooltip, TooltipContent, TooltipTrigger } from '@vmsh/ui'

/** Staff-only composition; docs/paste-evidence.md, review workspace/history. */
export function PasteEvidenceBadge({ estimate }: { estimate?: PasteEstimate | null | undefined }) {
  const triggerId = useId()
  const [open, setOpen] = useState(false)
  if (!estimate?.percentage) return null
  const percentage = estimate.percentage
  const description = t`Приблизительная доля текста, вставленного из буфера обмена. Не определяет использование ИИ.`
  const legacy = estimate.method === 'cumulative_pastes'
  return (
    <Tooltip open={open} onOpenChange={setOpen} triggerId={triggerId}>
      <TooltipTrigger
        id={triggerId}
        render={
          <button
            type="button"
            className="rounded-full"
            onClick={() => setOpen(true)}
            aria-label={
              legacy
                ? `${t`Вставлено ≈ ${percentage}%`}. ${description} ${t`Оценка не учитывает последующие удаления.`}`
                : `${t`Вставлено ≈ ${percentage}%`}. ${description}`
            }
          />
        }
      >
        <Badge variant={percentage >= 75 ? 'danger' : percentage >= 25 ? 'warning' : 'neutral'}>
          <Trans>Вставлено ≈ {percentage}%</Trans>
        </Badge>
      </TooltipTrigger>
      <TooltipContent role="tooltip">
        <div className="space-y-1">
          <p>{description}</p>
          {legacy ? (
            <p>
              <Trans>Оценка не учитывает последующие удаления.</Trans>
            </p>
          ) : null}
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
