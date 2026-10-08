import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import type { createStaffOralWindowClient } from '@vmsh/app-shell'
import { ApiResponseError, oralWindowBatchSchema, type StaffOralWindow } from '@vmsh/contracts'
import { Button, Card, CardContent, Input, Label } from '@vmsh/ui'

const entrySchema = z.object({
  id: z.string(),
  included: z.boolean(),
  groupLessonIds: z.array(z.string()),
  opensAt: z.string(),
  closesAt: z.string(),
  joinLabel: z.string(),
  joinUrl: z.string(),
  joinCode: z.string(),
})
const draftSchema = z.object({
  key: z.string(),
  locked: z.boolean(),
  entries: z.array(entrySchema).min(1).max(20),
})
type Entry = z.infer<typeof entrySchema>
type Draft = z.infer<typeof draftSchema>
type Client = ReturnType<typeof createStaffOralWindowClient>

function inputTime(date: Date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function copyOralWindow(window: StaffOralWindow, groupLessonIds: string[], days: number): Entry {
  return {
    id: crypto.randomUUID(),
    included: true,
    groupLessonIds,
    opensAt: inputTime(new Date(Date.parse(window.opensAt) + days * 86400000)),
    closesAt: inputTime(new Date(Date.parse(window.closesAt) + days * 86400000)),
    joinLabel: window.joinLabel,
    joinUrl: window.joinUrl,
    joinCode: window.joinCode ?? '',
  }
}
function blank(groupLessonId: string): Entry {
  const start = new Date()
  start.setHours(start.getHours() + 1, 0, 0, 0)
  return {
    id: crypto.randomUUID(),
    included: true,
    groupLessonIds: [groupLessonId],
    opensAt: inputTime(start),
    closesAt: inputTime(new Date(start.getTime() + 7200000)),
    joinLabel: t`Подключиться к Zoom`,
    joinUrl: '',
    joinCode: '',
  }
}
function load(key: string, groupLessonId: string, clone?: StaffOralWindow): Draft {
  if (clone)
    return {
      key: crypto.randomUUID(),
      locked: false,
      entries: [
        copyOralWindow(clone, clone.groups?.map((g) => g.groupLessonId) ?? [groupLessonId], 1),
      ],
    }
  try {
    const saved = draftSchema.safeParse(JSON.parse(localStorage.getItem(key) ?? 'null'))
    if (saved.success) return saved.data
  } catch {
    /* Keep a usable in-memory form. */
  }
  return { key: crypto.randomUUID(), locked: false, entries: [blank(groupLessonId)] }
}

/** oral-window-weekly-drafts.md: explicit editable batch, never automatic recurrence. */
export function OralWeeklyDraft({
  client,
  accountId,
  groupLessonId,
  clone,
  onSaved,
  onLockedChange,
}: {
  client: Client
  accountId: string
  groupLessonId: string
  clone?: StaffOralWindow | undefined
  onSaved: () => void
  onLockedChange?: ((locked: boolean) => void) | undefined
}) {
  const storageKey = `vmshpwa:staff:${accountId}:oral-weekly-draft:${groupLessonId}`
  const [draft, setDraft] = useState(() => load(storageKey, groupLessonId, clone))
  useEffect(() => {
    onLockedChange?.(draft.locked)
  }, [draft.locked, onLockedChange])
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const plan = useQuery({
    queryKey: ['oral-windows', 'planning', accountId, groupLessonId],
    queryFn: () => client.planning(groupLessonId),
  })
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(draft))
    } catch {
      /* The in-memory draft remains available. */
    }
  }, [draft, storageKey])
  const update = (entries: Entry[]) => {
    setDraft({ key: crypto.randomUUID(), locked: false, entries })
    setError(null)
    setSuccess(false)
  }
  const change = (id: string, patch: Partial<Entry>) =>
    update(draft.entries.map((e) => (e.id === id ? { ...e, ...patch } : e)))
  const mutation = useMutation({
    mutationFn: () =>
      client.saveBatch(
        groupLessonId,
        oralWindowBatchSchema.parse({
          schemaVersion: 1,
          idempotencyKey: draft.key,
          entries: draft.entries
            .filter((e) => e.included)
            .map((e) => ({
              groupLessonIds: e.groupLessonIds,
              window: {
                schemaVersion: 1,
                sequenceNumber: 1,
                opensAt: new Date(e.opensAt).toISOString(),
                closesAt: new Date(e.closesAt).toISOString(),
                joinLabel: e.joinLabel,
                joinUrl: e.joinUrl,
                joinCode: e.joinCode.trim() || null,
                status: 'active',
              },
            })),
        }),
      ),
    onSuccess: () => {
      setDraft({ key: crypto.randomUUID(), locked: false, entries: [blank(groupLessonId)] })
      setSuccess(true)
      setError(null)
      onSaved()
    },
    onError: (failure) => {
      const uncertain = !(failure instanceof ApiResponseError) || failure.status >= 500
      setDraft((d) => ({ ...d, locked: uncertain }))
      setError(
        failure instanceof ApiResponseError
          ? failure.message
          : t`Ответ сервера не получен. Повторите сохранение того же черновика — дубликатов не будет.`,
      )
    },
  })
  const save = () => {
    try {
      // Validate before locking, so invalid local fields remain editable.
      oralWindowBatchSchema.parse({
        schemaVersion: 1,
        idempotencyKey: draft.key,
        entries: draft.entries
          .filter((e) => e.included)
          .map((e) => ({
            groupLessonIds: e.groupLessonIds,
            window: {
              schemaVersion: 1,
              sequenceNumber: 1,
              opensAt: new Date(e.opensAt).toISOString(),
              closesAt: new Date(e.closesAt).toISOString(),
              joinLabel: e.joinLabel,
              joinUrl: e.joinUrl,
              joinCode: e.joinCode.trim() || null,
              status: 'active',
            },
          })),
      })
      const locked = { ...draft, locked: true }
      localStorage.setItem(storageKey, JSON.stringify(locked))
      setDraft(locked)
      setError(null)
      mutation.mutate()
    } catch {
      setError(
        t`Проверьте даты, HTTPS-ссылку и группы. Должно быть выбрано хотя бы одно окно. Для безопасного повтора также требуется доступное хранилище браузера.`,
      )
    }
  }
  const previous = () => {
    if (
      !plan.data?.previous.length ||
      !confirm(t`Заменить текущий черновик окнами прошлого занятия со сдвигом на 7 дней?`)
    )
      return
    update(plan.data.previous.map((e) => copyOralWindow(e.window, e.groupLessonIds, 7)))
  }
  const weekdays = () => {
    if (
      !confirm(
        t`Заменить черновик тремя окнами пн/вт/ср недели первой даты? Время, ссылка и группы берутся из первого окна.`,
      )
    )
      return
    const first = draft.entries[0]!
    const start = new Date(first.opensAt),
      end = new Date(first.closesAt)
    if (!Number.isFinite(+start) || !Number.isFinite(+end)) {
      setError(t`Сначала укажите корректные даты первого окна.`)
      return
    }
    const monday = new Date(start)
    monday.setDate(start.getDate() - ((start.getDay() + 6) % 7))
    update(
      [0, 1, 2].map((day) => {
        const date = new Date(monday)
        date.setDate(date.getDate() + day)
        return {
          ...first,
          id: crypto.randomUUID(),
          included: true,
          opensAt: inputTime(date),
          closesAt: inputTime(new Date(+date + (+end - +start))),
        }
      }),
    )
  }
  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <h2 className="font-semibold">
          <Trans>Черновик окон</Trans>
        </h2>
        {plan.data ? (
          <p className="text-small">
            <Trans>
              {plan.data.courseName} · занятие {plan.data.lessonNumber}
            </Trans>
          </p>
        ) : null}
        {plan.isError ? (
          <p role="alert">
            <Trans>Не удалось загрузить группы. </Trans>
            <Button variant="ghost" onClick={() => void plan.refetch()}>
              <Trans>Повторить</Trans>
            </Button>
          </p>
        ) : null}
        <p className="text-caption text-muted-foreground">
          <Trans>
            Время: {Intl.DateTimeFormat().resolvedOptions().timeZone}. Отметьте дни, которые нужно
            создать. Общие окна изменяются сразу для всех своих групп.
          </Trans>
        </p>
        <fieldset disabled={draft.locked || mutation.isPending} className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!plan.data?.previous.length}
              onClick={previous}
            >
              <Trans>С прошлого занятия (+7 дней)</Trans>
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={weekdays}>
              <Trans>Пн / вт / ср</Trans>
            </Button>
          </div>
          {draft.entries.map((entry, index) => (
            <fieldset key={entry.id} className="space-y-2 rounded-md border p-3">
              <legend>
                <label className="inline-flex min-h-11 items-center gap-2">
                  <input
                    type="checkbox"
                    checked={entry.included}
                    onChange={(e) => change(entry.id, { included: e.target.checked })}
                  />
                  <Trans>Окно</Trans> {index + 1}
                </label>
              </legend>
              <fieldset disabled={!entry.included} className="space-y-2">
                <div className="grid gap-2 sm:grid-cols-2">
                  {(['opensAt', 'closesAt'] as const).map((field) => (
                    <div key={field}>
                      <Label htmlFor={`${entry.id}-${field}`}>
                        {field === 'opensAt' ? t`Открывается` : t`Закрывается`}
                      </Label>
                      <Input
                        id={`${entry.id}-${field}`}
                        type="datetime-local"
                        value={entry[field]}
                        onChange={(e) => change(entry.id, { [field]: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-x-4">
                  {plan.data?.groups.map((group) => (
                    <label
                      key={group.groupLessonId}
                      className="inline-flex min-h-11 items-center gap-2"
                    >
                      <input
                        type="checkbox"
                        checked={entry.groupLessonIds.includes(group.groupLessonId)}
                        onChange={(e) =>
                          change(entry.id, {
                            groupLessonIds: e.target.checked
                              ? [...entry.groupLessonIds, group.groupLessonId]
                              : entry.groupLessonIds.filter((id) => id !== group.groupLessonId),
                          })
                        }
                      />
                      {group.groupName}
                    </label>
                  ))}
                </div>
                {(
                  [
                    { field: 'joinLabel', label: t`Подпись кнопки` },
                    { field: 'joinUrl', label: t`HTTPS-ссылка` },
                    { field: 'joinCode', label: t`Код, если нужен` },
                  ] as const
                ).map(({ field, label }) => (
                  <div key={field}>
                    <Label htmlFor={`${entry.id}-${field}`}>{label}</Label>
                    <Input
                      id={`${entry.id}-${field}`}
                      value={entry[field]}
                      onChange={(e) => change(entry.id, { [field]: e.target.value })}
                    />
                  </div>
                ))}
              </fieldset>
            </fieldset>
          ))}
          <Button
            type="button"
            variant="ghost"
            disabled={draft.entries.length >= 20}
            onClick={() => update([...draft.entries, blank(groupLessonId)])}
          >
            <Trans>Добавить ещё окно</Trans>
          </Button>
        </fieldset>
        {error ? (
          <p role="alert" className="text-small text-destructive">
            {error}
          </p>
        ) : null}
        {draft.locked && !mutation.isPending ? (
          <p className="text-small">
            <Trans>Сначала подтвердите сохранение этого черновика повторным запросом.</Trans>
          </p>
        ) : null}
        {success ? (
          <p role="status" className="text-small">
            <Trans>Окна созданы для выбранных групп.</Trans>
          </p>
        ) : null}
        <Button disabled={mutation.isPending || !plan.data} onClick={save}>
          {mutation.isPending
            ? t`Сохраняем…`
            : draft.locked
              ? t`Повторить сохранение`
              : t`Создать выбранные окна`}
        </Button>
      </CardContent>
    </Card>
  )
}
