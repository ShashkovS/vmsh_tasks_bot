import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useState, type ReactNode } from 'react'
import { ChevronDown, ChevronUp, KeyRound, Lightbulb } from 'lucide-react'
import { Button } from '@vmsh/ui'

type Kind = 'hint' | 'solution'
export interface WorksheetMaterial {
  available: boolean
  confirmationRequired?: boolean
  load: () => Promise<ReactNode>
  preview?: ReactNode
}
/** Shared Student/Staff disclosure; see docs/worksheet-materials.md. */
export function WorksheetMaterials({
  hint,
  solution,
  compact = false,
  defaultOpen,
}: {
  hint: WorksheetMaterial
  solution: WorksheetMaterial
  compact?: boolean
  defaultOpen?: Kind
}) {
  const [opened, setOpened] = useState<Kind | null>(defaultOpen ?? null)
  const [confirming, setConfirming] = useState(false)
  const [contents, setContents] = useState<Partial<Record<Kind, ReactNode>>>({})
  const [loading, setLoading] = useState<Kind | null>(null)
  const [error, setError] = useState(false)
  const materials = { hint, solution }
  // docs/figure-layout.md: StaffWorksheetPreview supplies a live editor preview.
  // Cache student loads only; editor tools and figure drafts arrive after mount.
  const visibleContents = {
    hint: hint.preview ?? contents.hint,
    solution: solution.preview ?? contents.solution,
  }
  const open = async (kind: Kind) => {
    setConfirming(false)
    setOpened(kind)
    setError(false)
    if (visibleContents[kind] != null) return
    setLoading(kind)
    try {
      const content = await materials[kind].load()
      setContents((current) => ({ ...current, [kind]: content }))
    } catch {
      setError(true)
    } finally {
      setLoading(null)
    }
  }
  const toggle = (kind: Kind) => {
    if (loading) return
    if (opened === kind) {
      setOpened(null)
      setConfirming(false)
      return
    }
    if (kind === 'hint' && hint.confirmationRequired && visibleContents.hint == null) {
      setOpened(null)
      setConfirming(true)
      setError(false)
    } else {
      void open(kind)
    }
  }
  return (
    <div
      role="group"
      aria-label={t`Подсказка и решение`}
      className={compact ? 'contents font-sans' : 'mt-4 font-sans'}
    >
      <div className={compact ? 'contents' : 'flex flex-wrap gap-1.5'}>
        {(['hint', 'solution'] as const).map((kind) =>
          materials[kind].available ? (
            <Button
              key={kind}
              data-print-hide
              aria-expanded={opened === kind}
              disabled={loading !== null}
              onClick={() => toggle(kind)}
              size="sm"
              variant="ghost"
            >
              {kind === 'hint' ? (
                <Lightbulb aria-hidden="true" className="size-4" />
              ) : (
                <KeyRound aria-hidden="true" className="size-4" />
              )}
              {kind === 'hint' ? t`Подсказка` : t`Решение`}
              {opened === kind ? (
                <ChevronUp aria-hidden="true" />
              ) : (
                <ChevronDown aria-hidden="true" />
              )}
            </Button>
          ) : null,
        )}
      </div>
      {confirming ? (
        <div
          data-print-hide
          className="order-3 mt-2 w-full basis-full rounded-md border border-border p-3 text-small"
        >
          <p>
            <Trans>Показать подсказку? После открытия её уже не получится развидеть.</Trans>
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void open('hint')}>
              <Trans>Показать подсказку</Trans>
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              <Trans>Отмена</Trans>
            </Button>
          </div>
        </div>
      ) : null}
      {loading ? (
        <p role="status" data-print-hide className="order-3 w-full basis-full text-small">
          <Trans>Загружаем…</Trans>
        </p>
      ) : null}
      {error ? (
        <div
          role="alert"
          data-print-hide
          className="order-3 w-full basis-full text-small text-danger"
        >
          <Trans>Не удалось открыть материал. Проверьте соединение и повторите попытку.</Trans>
          <Button size="sm" variant="ghost" onClick={() => opened && void open(opened)}>
            <Trans>Повторить</Trans>
          </Button>
        </div>
      ) : null}
      {opened && visibleContents[opened] != null ? (
        <div
          data-material-kind={opened}
          className="vmsh-material-reveal order-3 mt-2 w-full basis-full border-l-2 border-border pl-3"
        >
          {opened === 'hint' ? (
            <p className="vmsh-material-label text-small font-medium">
              <Trans>Подсказка</Trans>
            </p>
          ) : (
            // docs/worksheet-print.md: retain the print label without duplicating the screen disclosure.
            <p className="vmsh-material-label hidden text-small font-medium print:block">
              <Trans>Решение</Trans>
            </p>
          )}
          {visibleContents[opened]}
          <div className="mt-2 font-sans" data-print-hide>
            <Button size="sm" variant="ghost" onClick={() => setOpened(null)}>
              <ChevronUp aria-hidden="true" />
              {opened === 'hint' ? t`Скрыть подсказку` : t`Скрыть решение`}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
