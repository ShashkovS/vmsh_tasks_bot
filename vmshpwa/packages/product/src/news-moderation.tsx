import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import { Clock3, Eye, EyeOff, Images, Pencil, RefreshCcw, Send, Trash2, Unlink } from 'lucide-react'

import type { StaffNewsItem } from '@vmsh/contracts'
import { Badge, Button, Card, CardContent } from '@vmsh/ui'

function formatMoment(value: string): string {
  return dateTimeFormat(currentLocale(), {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

const visibilityCopy = {
  visible: {
    get label() {
      return t`В ленте`
    },
    variant: 'success' as const,
    Icon: Eye,
  },
  manual_hidden: {
    get label() {
      return t`Скрыто в PWA`
    },
    variant: 'warning' as const,
    Icon: EyeOff,
  },
  source_deleted: {
    get label() {
      return t`Удалено в Telegram`
    },
    variant: 'neutral' as const,
    Icon: Trash2,
  },
}

export function NewsModerationList({
  items,
  pendingPostId,
  onHide,
  onEdit,
  onMarkSourceDeleted,
  onMarkSourcePresent,
  onRestore,
}: {
  items: StaffNewsItem[]
  pendingPostId?: string | null
  onHide?: (item: StaffNewsItem) => void
  onEdit?: (item: StaffNewsItem) => void
  onMarkSourceDeleted?: (item: StaffNewsItem) => void
  onMarkSourcePresent?: (item: StaffNewsItem) => void
  onRestore?: (item: StaffNewsItem) => void
}) {
  return (
    <ul className="space-y-2">
      {items.map((item) => {
        const state = item.isScheduled
          ? { label: t`По расписанию`, variant: 'info' as const, Icon: Clock3 }
          : visibilityCopy[item.visibility]
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
                      {item.ownerName} · {item.channelTitle ?? t`Локальная публикация`}
                    </span>
                    <Badge variant="outline">
                      {item.audience === 'both'
                        ? t`Школьник и родитель`
                        : item.audience === 'student'
                          ? t`Только школьник`
                          : t`Только родитель`}
                    </Badge>
                    <Badge variant="outline">
                      {item.attendanceMode === 'all'
                        ? t`Очно и онлайн`
                        : item.attendanceMode === 'in_person'
                          ? t`Только очные`
                          : t`Только онлайн`}
                    </Badge>
                    {item.mediaCount > 0 ? (
                      <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
                        <Images aria-hidden="true" className="size-3.5" />
                        {item.mediaCount}
                      </span>
                    ) : null}
                  </div>
                  <p className="line-clamp-2 whitespace-pre-wrap text-small text-foreground">
                    {item.textExcerpt || t`Публикация без текста`}
                  </p>
                  <p className="text-caption text-muted-foreground">
                    {formatMoment(item.publishedAt)} <Trans>· ревизия {item.revision}</Trans>
                    {item.editedAt ? t` · обновлено ${formatMoment(item.editedAt)}` : ''}
                    {item.moderationReason ? ` · ${item.moderationReason}` : ''}
                  </p>
                </div>
                <div className="flex justify-end gap-2">
                  {item.source === 'local' && onEdit ? (
                    <Button
                      aria-label={t`${item.isScheduled ? t`Изменить запланированную` : t`Исправить опубликованную`} публикацию ${item.postId}`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onEdit(item)}
                      size="sm"
                      variant="outline"
                    >
                      <Pencil aria-hidden="true" />
                      <Trans>Изменить</Trans>
                    </Button>
                  ) : null}
                  {item.visibility === 'visible' && onHide ? (
                    <Button
                      aria-label={t`Скрыть публикацию ${item.postId} в PWA`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onHide(item)}
                      size="sm"
                      variant="outline"
                    >
                      <EyeOff aria-hidden="true" />
                      <Trans>Скрыть</Trans>
                    </Button>
                  ) : null}
                  {item.visibility === 'manual_hidden' && onRestore ? (
                    <Button
                      aria-label={t`Вернуть публикацию ${item.postId} в PWA`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onRestore(item)}
                      size="sm"
                      variant="outline"
                    >
                      <Send aria-hidden="true" />
                      <Trans>Вернуть</Trans>
                    </Button>
                  ) : null}
                  {item.source === 'telegram' &&
                  item.visibility !== 'source_deleted' &&
                  onMarkSourceDeleted ? (
                    <Button
                      aria-label={t`Отметить публикацию ${item.postId} удалённой в Telegram`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onMarkSourceDeleted(item)}
                      size="sm"
                      variant="ghost"
                    >
                      <Unlink aria-hidden="true" />
                      <Trans>Нет в Telegram</Trans>
                    </Button>
                  ) : null}
                  {item.source === 'telegram' &&
                  item.visibility === 'source_deleted' &&
                  onMarkSourcePresent ? (
                    <Button
                      aria-label={t`Отметить публикацию ${item.postId} доступной в Telegram`}
                      disabled={pendingPostId === item.postId}
                      onClick={() => onMarkSourcePresent(item)}
                      size="sm"
                      variant="outline"
                    >
                      <RefreshCcw aria-hidden="true" />
                      <Trans>Пост доступен</Trans>
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
