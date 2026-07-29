import { Eye, EyeOff, Images, Send, Trash2 } from 'lucide-react'

import type { StaffNewsItem } from '@vmsh/contracts'
import { Badge, Button, Card, CardContent } from '@vmsh/ui'

function formatMoment(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

const visibilityCopy = {
  visible: { label: 'В ленте', variant: 'success' as const, Icon: Eye },
  manual_hidden: { label: 'Скрыто в PWA', variant: 'warning' as const, Icon: EyeOff },
  source_deleted: { label: 'Удалено в Telegram', variant: 'neutral' as const, Icon: Trash2 },
}

export function NewsModerationList({
  items,
  pendingPostId,
  onHide,
  onRestore,
}: {
  items: StaffNewsItem[]
  pendingPostId?: string | null
  onHide?: (item: StaffNewsItem) => void
  onRestore?: (item: StaffNewsItem) => void
}) {
  return (
    <ul className="space-y-2">
      {items.map((item) => {
        const state = visibilityCopy[item.visibility]
        const StateIcon = state.Icon
        return (
          <li key={item.postId}>
            <Card size="sm">
              <CardContent className="grid gap-3 pt-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={state.variant}>
                      <StateIcon aria-hidden="true" />
                      {state.label}
                    </Badge>
                    <span className="text-caption text-muted-foreground">
                      {item.ownerName} · {item.channelTitle ?? 'Локальная публикация'}
                    </span>
                    {item.mediaCount > 0 ? (
                      <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
                        <Images aria-hidden="true" className="size-3.5" />
                        {item.mediaCount}
                      </span>
                    ) : null}
                  </div>
                  <p className="line-clamp-2 whitespace-pre-wrap text-small text-foreground">
                    {item.textExcerpt || 'Публикация без текста'}
                  </p>
                  <p className="text-caption text-muted-foreground">
                    {formatMoment(item.publishedAt)} · ревизия {item.revision}
                    {item.moderationReason ? ` · ${item.moderationReason}` : ''}
                  </p>
                </div>
                <div className="flex justify-end gap-2">
                  {item.visibility === 'visible' && onHide ? (
                    <Button
                      aria-label={`Скрыть публикацию ${item.postId} в PWA`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onHide(item)}
                      size="sm"
                      variant="outline"
                    >
                      <EyeOff aria-hidden="true" />
                      Скрыть
                    </Button>
                  ) : null}
                  {item.visibility === 'manual_hidden' && onRestore ? (
                    <Button
                      aria-label={`Вернуть публикацию ${item.postId} в PWA`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onRestore(item)}
                      size="sm"
                      variant="outline"
                    >
                      <Send aria-hidden="true" />
                      Вернуть
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}
