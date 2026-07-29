import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createStaffOralWindowClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffOralWindowsQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  oralWindowQueryKeys,
  type SaveOralWindowRequest,
  type StaffOralWindow,
} from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  Button,
  Card,
  CardContent,
  Input,
  Label,
} from '@vmsh/ui'

interface OralWindowDraft {
  sequenceNumber: string
  opensAt: string
  closesAt: string
  joinLabel: string
  joinUrl: string
  joinCode: string
}

function localInputTime(date: Date): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function newDraft(): OralWindowDraft {
  const opensAt = new Date()
  opensAt.setMinutes(0, 0, 0)
  opensAt.setHours(opensAt.getHours() + 1)
  return {
    sequenceNumber: '1',
    opensAt: localInputTime(opensAt),
    closesAt: localInputTime(new Date(opensAt.getTime() + 2 * 60 * 60_000)),
    joinLabel: 'Подключиться к Zoom',
    joinUrl: '',
    joinCode: '',
  }
}

function readDraft(key: string): OralWindowDraft {
  try {
    const parsed: unknown = JSON.parse(globalThis.localStorage.getItem(key) ?? 'null')
    if (
      parsed &&
      typeof parsed === 'object' &&
      'sequenceNumber' in parsed &&
      typeof parsed.sequenceNumber === 'string' &&
      'opensAt' in parsed &&
      typeof parsed.opensAt === 'string' &&
      'closesAt' in parsed &&
      typeof parsed.closesAt === 'string' &&
      'joinLabel' in parsed &&
      typeof parsed.joinLabel === 'string' &&
      'joinUrl' in parsed &&
      typeof parsed.joinUrl === 'string' &&
      'joinCode' in parsed &&
      typeof parsed.joinCode === 'string'
    ) {
      return {
        sequenceNumber: parsed.sequenceNumber,
        opensAt: parsed.opensAt,
        closesAt: parsed.closesAt,
        joinLabel: parsed.joinLabel,
        joinUrl: parsed.joinUrl,
        joinCode: parsed.joinCode,
      }
    }
  } catch {
    // A denied or corrupt localStorage must not block the editor.
  }
  return newDraft()
}

function requestFromDraft(draft: OralWindowDraft): SaveOralWindowRequest {
  return {
    schemaVersion: 1,
    sequenceNumber: Number(draft.sequenceNumber),
    opensAt: new Date(draft.opensAt).toISOString(),
    closesAt: new Date(draft.closesAt).toISOString(),
    joinLabel: draft.joinLabel,
    joinUrl: draft.joinUrl,
    joinCode: draft.joinCode.trim() || null,
    status: 'active',
  }
}

function draftFromWindow(window: StaffOralWindow): OralWindowDraft {
  return {
    sequenceNumber: String(window.sequenceNumber),
    opensAt: localInputTime(new Date(window.opensAt)),
    closesAt: localInputTime(new Date(window.closesAt)),
    joinLabel: window.joinLabel,
    joinUrl: window.joinUrl,
    joinCode: window.joinCode ?? '',
  }
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function StaffOralWindowsPage({ groupLessonId }: { groupLessonId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Oral windows require Staff auth')
  const allowed = principal.role === 'admin' && principal.capabilities.includes('oral.manage')
  const storageKey = `vmshpwa:staff:${principal.accountId}:oral-window-draft:${groupLessonId}`
  const [draft, setDraft] = useState<OralWindowDraft>(() => readDraft(storageKey))
  const [editing, setEditing] = useState<{ windowId: string; version: number } | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const client = useMemo(
    () =>
      createStaffOralWindowClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const queryClient = useQueryClient()
  const queryKey = oralWindowQueryKeys.staff(principal, groupLessonId)
  const query = useStaffOralWindowsQuery(client, principal, groupLessonId, allowed)

  useEffect(() => {
    try {
      globalThis.localStorage.setItem(storageKey, JSON.stringify(draft))
    } catch {
      // Keep the in-memory draft when browser storage is unavailable.
    }
  }, [draft, storageKey])

  const mutation = useMutation({
    mutationFn: async (
      command:
        | { kind: 'save'; input: SaveOralWindowRequest }
        | { kind: 'cancel'; window: StaffOralWindow },
    ) => {
      if (command.kind === 'cancel') {
        return client.update(command.window.windowId, command.window.version, {
          schemaVersion: 1,
          sequenceNumber: command.window.sequenceNumber,
          opensAt: command.window.opensAt,
          closesAt: command.window.closesAt,
          joinLabel: command.window.joinLabel,
          joinUrl: command.window.joinUrl,
          joinCode: command.window.joinCode,
          status: 'cancelled',
        })
      }
      return editing
        ? client.update(editing.windowId, editing.version, command.input)
        : client.create(groupLessonId, command.input)
    },
    onSuccess: async () => {
      const cleanDraft = newDraft()
      setDraft(cleanDraft)
      setEditing(null)
      setValidationError(null)
      try {
        globalThis.localStorage.removeItem(storageKey)
      } catch {
        // The successful server write is authoritative.
      }
      await queryClient.invalidateQueries({ queryKey })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (!allowed) {
    return (
      <PageLayout title="Устный приём" width="wide">
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }

  const save = (event: FormEvent) => {
    event.preventDefault()
    try {
      const input = requestFromDraft(draft)
      if (!Number.isInteger(input.sequenceNumber) || input.sequenceNumber < 1) {
        throw new Error('invalid sequence')
      }
      if (input.closesAt <= input.opensAt || !input.joinLabel.trim() || !input.joinUrl.trim()) {
        throw new Error('invalid window')
      }
      if (new URL(input.joinUrl).protocol !== 'https:') throw new Error('invalid URL')
      setValidationError(null)
      mutation.mutate({ kind: 'save', input })
    } catch {
      setValidationError('Проверьте номер, время, подпись и HTTPS-ссылку.')
    }
  }

  return (
    <PageLayout
      description="Несколько независимых окон для одного группового занятия. Ссылка показывается школьнику только во время открытого окна."
      eyebrow={`Групповое занятие ${groupLessonId}`}
      title="Устный приём"
      width="wide"
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(20rem,0.8fr)_minmax(28rem,1.2fr)]">
        <Card>
          <CardContent className="pt-4">
            <form className="space-y-3" onSubmit={save}>
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-semibold">{editing ? 'Изменить окно' : 'Новое окно'}</h2>
                {editing ? (
                  <Button
                    onClick={() => {
                      setEditing(null)
                      setDraft(newDraft())
                    }}
                    size="xs"
                    type="button"
                    variant="ghost"
                  >
                    Отмена
                  </Button>
                ) : null}
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1">
                  <Label htmlFor="oral-sequence">Номер</Label>
                  <Input
                    id="oral-sequence"
                    min="1"
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, sequenceNumber: event.target.value }))
                    }
                    type="number"
                    value={draft.sequenceNumber}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="oral-opens">Открывается</Label>
                  <Input
                    id="oral-opens"
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, opensAt: event.target.value }))
                    }
                    type="datetime-local"
                    value={draft.opensAt}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="oral-closes">Закрывается</Label>
                  <Input
                    id="oral-closes"
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, closesAt: event.target.value }))
                    }
                    type="datetime-local"
                    value={draft.closesAt}
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="oral-label">Подпись кнопки</Label>
                <Input
                  id="oral-label"
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, joinLabel: event.target.value }))
                  }
                  value={draft.joinLabel}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="oral-url">HTTPS-ссылка</Label>
                <Input
                  id="oral-url"
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, joinUrl: event.target.value }))
                  }
                  placeholder="https://zoom.us/j/…"
                  type="url"
                  value={draft.joinUrl}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="oral-code">Код, если нужен</Label>
                <Input
                  id="oral-code"
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, joinCode: event.target.value }))
                  }
                  value={draft.joinCode}
                />
              </div>
              <p className="text-caption text-muted-foreground">
                Черновик формы сохраняется на этом устройстве автоматически.
              </p>
              {validationError ? (
                <p className="text-small text-destructive" role="alert">
                  {validationError}
                </p>
              ) : null}
              {mutation.error ? (
                <p className="text-small text-destructive" role="alert">
                  {mutation.error instanceof ApiResponseError
                    ? mutation.error.message
                    : 'Не удалось сохранить окно.'}
                </p>
              ) : null}
              <Button disabled={mutation.isPending} type="submit">
                {mutation.isPending ? 'Сохраняем…' : editing ? 'Сохранить' : 'Добавить окно'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <section aria-label="Настроенные окна" className="space-y-2">
          {query.isPending ? <PageStatePanel state="loading" /> : null}
          {query.error ? <PageStatePanel state="error" /> : null}
          {query.data?.items.length === 0 ? (
            <Alert tone="info">
              <AlertContent>
                <AlertDescription>Для занятия ещё нет окон устного приёма.</AlertDescription>
              </AlertContent>
            </Alert>
          ) : null}
          {query.data?.items.map((window) => (
            <Card key={window.windowId}>
              <CardContent className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-medium">
                    Окно {window.sequenceNumber} ·{' '}
                    {window.state === 'open' ? 'открыто' : window.state}
                  </p>
                  <p className="font-num text-small text-muted-foreground">
                    {dateLabel(window.opensAt)} — {dateLabel(window.closesAt)}
                  </p>
                  <p className="mt-1 truncate text-small">{window.joinUrl}</p>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => {
                      setEditing({ windowId: window.windowId, version: window.version })
                      setDraft(draftFromWindow(window))
                    }}
                    size="sm"
                    variant="outline"
                  >
                    Изменить
                  </Button>
                  {window.status === 'active' ? (
                    <Button
                      onClick={() => mutation.mutate({ kind: 'cancel', window })}
                      size="sm"
                      variant="ghost"
                    >
                      Отменить
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </section>
      </div>
    </PageLayout>
  )
}
