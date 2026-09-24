import { Badge } from '@vmsh/ui'

/**
 * Calm, non-blocking acknowledgement after realtime replaces published content.
 * See `dev/development-plan/06-phase-2-content.md` and
 * `packages/content/src/content-update.ts`.
 */
export function ContentUpdateMarker({ visible }: { visible: boolean }) {
  if (!visible) return null
  return (
    <p
      aria-live="polite"
      className="mb-4 flex flex-wrap items-center gap-2 text-small text-muted-foreground"
      role="status"
    >
      <Badge variant="info">Материал обновлён</Badge>
      Открыта новая опубликованная версия.
    </p>
  )
}
