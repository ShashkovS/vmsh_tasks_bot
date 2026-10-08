import { Trans } from '@lingui/react/macro'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import { t } from '@lingui/core/macro'
import { useMemo, useRef, useState } from 'react'

import {
  createLessonBlockClient,
  useAuthentication,
  useStaffLessonBlocksQuery,
  type LessonBlockClient,
} from '@vmsh/app-shell'
import type { LessonBlockPosition, StaffLessonBlock } from '@vmsh/contracts'
import { LessonRichDocumentView, parseLessonRichMarkdown } from '@vmsh/product'
import { Button, Card, CardContent, Input, Label } from '@vmsh/ui'

import { LessonVideoDialog } from './lesson-video-dialog'
import { StaffFileUpload } from './staff-file-upload'

function formatPublishedAt(value: string | null): string {
  if (value === null) return t`не опубликован`
  return dateTimeFormat(currentLocale(), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function scheduleInstant(value: string, timezone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/u.exec(value)
  if (!match) throw new Error(t`Укажите время публикации в часовом поясе занятия.`)

  const wanted = `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}`
  const formatter = new Intl.DateTimeFormat('sv-SE', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
  const base = Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4]),
    Number(match[5]),
  )
  const candidates: number[] = []
  for (let minutes = -14 * 60; minutes <= 14 * 60; minutes += 15) {
    const candidate = base + minutes * 60_000
    const parts = Object.fromEntries(
      formatter
        .formatToParts(candidate)
        .filter((part) => ['year', 'month', 'day', 'hour', 'minute'].includes(part.type))
        .map((part) => [part.type, part.value]),
    )
    if (`${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}` === wanted) {
      candidates.push(candidate)
    }
  }
  if (candidates.length === 0) {
    throw new Error(t`Такого времени нет в часовом поясе занятия. Выберите другое время.`)
  }
  if (candidates.length !== 1) {
    throw new Error(t`Это время неоднозначно в часовом поясе занятия. Выберите другое время.`)
  }
  return new Date(candidates[0] ?? base).toISOString()
}

export function StaffLessonBlockEditor({
  block,
  businessTimezone,
  client,
  groupLessonId,
  position,
  refetch,
  title,
}: {
  block: StaffLessonBlock | null
  businessTimezone: string
  client: LessonBlockClient
  groupLessonId: string
  position: LessonBlockPosition
  refetch: () => Promise<unknown>
  title: string
}) {
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [mode, setMode] = useState<'now' | 'scheduled' | 'with_lesson'>('now')
  const [scheduledAt, setScheduledAt] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const [isMutating, setIsMutating] = useState(false)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const value = markdown ?? block?.draft?.markdown ?? ''
  const parsed = useMemo(() => {
    if (!value.trim()) return { document: null, error: null }
    try {
      return { document: parseLessonRichMarkdown(value), error: null }
    } catch (error) {
      return {
        document: null,
        error: error instanceof Error ? error.message : t`Не удалось разобрать Markdown`,
      }
    }
  }, [value])
  const etag = block?.etag ?? '"none"'
  const hasUnsavedChanges = markdown !== null

  const run = async (operation: () => Promise<void>) => {
    setIsMutating(true)
    try {
      await operation()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t`Не удалось изменить блок занятия`)
    } finally {
      setIsMutating(false)
    }
  }

  const save = () =>
    run(async () => {
      if (parsed.error) return
      await client.save(groupLessonId, position, etag, {
        markdown: value,
        document: parsed.document,
      })
      setMarkdown(null)
      setMessage(t`Черновик сохранён.`)
      await refetch()
    })

  const publish = () =>
    run(async () => {
      const revisionId = block?.draft?.revisionId
      if (!revisionId) {
        setMessage(t`Сначала сохраните черновик.`)
        return
      }
      await client.publish(groupLessonId, position, etag, {
        revisionId,
        mode,
        scheduledAt: mode === 'scheduled' ? scheduleInstant(scheduledAt, businessTimezone) : null,
      })
      setMessage(t`Настройки публикации сохранены.`)
      await refetch()
    })

  const insert = (valueToInsert: string) => setMarkdown(`${value}${valueToInsert}`)

  const uploadImage = async (image: File) => {
    setIsUploadingImage(true)
    try {
      const uploaded = await client.uploadImage(groupLessonId, image)
      const alt =
        image.name
          .replace(/\.[^.]+$/u, '')
          .replaceAll('[', '')
          .replaceAll(']', '') || t`Картинка`
      insert(`\n\n![${alt}](${uploaded.url})\n`)
      setMessage(t`Картинка загружена; сохраните черновик, чтобы закрепить её в версии.`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t`Не удалось загрузить картинку`)
    } finally {
      setIsUploadingImage(false)
    }
  }

  return (
    <Card className="gap-0 py-0">
      <details>
        <summary className="cursor-pointer px-4 py-3 text-small font-medium">
          {title}
          <span className="ml-3 font-normal text-muted-foreground">
            {hasUnsavedChanges
              ? t`Есть изменения`
              : block?.published
                ? t`Опубликован`
                : block?.draft
                  ? t`Черновик`
                  : t`Не добавлен`}
          </span>
        </summary>
        <CardContent className="space-y-3 border-t border-border py-4">
          <p className="text-small text-muted-foreground">
            <Trans>Опубликованная версия: </Trans>
            {block?.published
              ? `№${block.published.revisionNumber}, ${formatPublishedAt(block.publishedAt)}`
              : t`нет`}
            {block?.pending
              ? t` · ожидает версия №${block.pending.revisionNumber}${
                  block.pendingMode === 'scheduled' && block.scheduledAt
                    ? `: ${formatPublishedAt(block.scheduledAt)}`
                    : t` вместе с занятием`
                }`
              : ''}
          </p>
          <textarea
            ref={textarea}
            aria-label={`${title}: Markdown`}
            className="min-h-32 w-full rounded-md border border-input bg-surface p-3 font-mono text-small"
            onChange={(event) => setMarkdown(event.target.value)}
            value={value}
          />
          {hasUnsavedChanges ? (
            <p className="text-small text-status-warning" role="status">
              <Trans>Есть несохранённые изменения.</Trans>
            </p>
          ) : null}
          <div className="flex flex-wrap items-start gap-2">
            <Label className="cursor-pointer rounded-md border border-input px-3 py-2 text-small">
              {isUploadingImage ? t`Готовим картинку…` : t`Загрузить картинку`}
              <input
                accept="image/png,image/jpeg,image/webp"
                className="sr-only"
                disabled={isUploadingImage || isMutating}
                onChange={(event) => {
                  const image = event.target.files?.[0]
                  event.target.value = ''
                  if (image) void uploadImage(image)
                }}
                type="file"
              />
            </Label>
            <LessonVideoDialog onInsert={insert} />
          </div>
          <StaffFileUpload
            disabled={isMutating}
            onUpload={(file) => client.uploadFile(groupLessonId, file)}
            onInsert={(attachment) => {
              // Read the live textarea after upload; rich-file-attachments.md.
              const current = textarea.current
              if (!current) return
              const start = current.selectionStart
              const end = current.selectionEnd
              setMarkdown(
                `${current.value.slice(0, start)}${attachment}${current.value.slice(end)}`,
              )
              current.focus()
              requestAnimationFrame(() =>
                current.setSelectionRange(start + attachment.length, start + attachment.length),
              )
            }}
          />
          {parsed.error ? (
            <p className="text-small text-status-error" role="alert">
              {parsed.error}
            </p>
          ) : parsed.document ? (
            <section aria-label={t`Предпросмотр черновика`} className="space-y-2">
              <p className="text-small font-medium">
                <Trans>Предпросмотр черновика</Trans>
              </p>
              <LessonRichDocumentView
                document={parsed.document}
                idPrefix={`staff-draft-${groupLessonId}-${position}`}
              />
            </section>
          ) : null}
          {block?.published?.document ? (
            <details className="rounded-md border border-border p-3">
              <summary className="cursor-pointer text-small font-medium">
                <Trans>Предпросмотр опубликованной версии</Trans>
              </summary>
              <LessonRichDocumentView
                document={block.published.document}
                idPrefix={`staff-published-${groupLessonId}-${position}`}
              />
            </details>
          ) : null}
          <div className="grid gap-2 sm:grid-cols-2">
            <Label className="flex-col items-start leading-normal">
              <Trans>Публикация</Trans>
              <select
                className="min-h-10 rounded-md border border-input bg-surface px-3"
                onChange={(event) => setMode(event.target.value as typeof mode)}
                value={mode}
              >
                <option value="now">
                  <Trans>Сейчас</Trans>
                </option>
                <option value="with_lesson">
                  <Trans>Вместе с занятием</Trans>
                </option>
                <option value="scheduled">
                  <Trans>По расписанию</Trans>
                </option>
              </select>
            </Label>
            {mode === 'scheduled' ? (
              <Label className="flex-col items-start leading-normal">
                <Trans>Время ({businessTimezone})</Trans>
                <Input
                  onChange={(event) => setScheduledAt(event.target.value)}
                  type="datetime-local"
                  value={scheduledAt}
                />
              </Label>
            ) : null}
          </div>
          <div className="flex flex-wrap items-start gap-2">
            <Button disabled={isMutating || Boolean(parsed.error)} onClick={save} size="sm">
              <Trans>Сохранить черновик</Trans>
            </Button>
            <Button
              disabled={isMutating || !block?.draft || hasUnsavedChanges}
              onClick={publish}
              size="sm"
              variant="outline"
            >
              <Trans>Применить публикацию</Trans>
            </Button>
            {block?.pending ? (
              <Button
                disabled={isMutating}
                onClick={() =>
                  void run(async () => {
                    await client.cancel(groupLessonId, position, etag)
                    setMessage(t`Отложенная публикация отменена.`)
                    await refetch()
                  })
                }
                size="sm"
                variant="outline"
              >
                <Trans>Отменить отложенную публикацию</Trans>
              </Button>
            ) : null}
            {block?.published ? (
              <Button
                disabled={isMutating}
                onClick={() =>
                  void run(async () => {
                    await client.hide(groupLessonId, position, etag)
                    setMessage(t`Опубликованная версия скрыта.`)
                    await refetch()
                  })
                }
                size="sm"
                variant="outline"
              >
                <Trans>Скрыть</Trans>
              </Button>
            ) : null}
          </div>
          {message ? (
            <p className="text-small text-muted-foreground" role="status">
              {message}
            </p>
          ) : null}
        </CardContent>
      </details>
    </Card>
  )
}

export function StaffLessonBlocksEditor({ groupLessonId }: { groupLessonId: string }) {
  const authentication = useAuthentication()
  const client = useMemo(
    () =>
      createLessonBlockClient(authentication.client.runtime, {
        refreshSession: authentication.refresh,
      }),
    [authentication],
  )
  const query = useStaffLessonBlocksQuery(client, groupLessonId)

  if (query.isPending) {
    return (
      <p className="text-small text-muted-foreground">
        <Trans>Загружаем блоки занятия…</Trans>
      </p>
    )
  }
  if (query.isError || !query.data) {
    return (
      <Card>
        <CardContent className="space-y-2 p-4">
          <p className="text-small text-status-error">
            <Trans>Не удалось загрузить блоки занятия.</Trans>
          </p>
          <Button onClick={() => void query.refetch()} size="sm" variant="outline">
            <Trans>Повторить</Trans>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <section className="space-y-4">
      <StaffLessonBlockEditor
        block={query.data.before}
        businessTimezone={query.data.businessTimezone}
        client={client}
        groupLessonId={groupLessonId}
        position="before"
        refetch={query.refetch}
        title={t`Блок перед задачами`}
      />
      <StaffLessonBlockEditor
        block={query.data.after}
        businessTimezone={query.data.businessTimezone}
        client={client}
        groupLessonId={groupLessonId}
        position="after"
        refetch={query.refetch}
        title={t`Блок после задач`}
      />
    </section>
  )
}
