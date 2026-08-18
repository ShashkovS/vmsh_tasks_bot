import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, Plus } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  ClassroomNetworkError,
  PageStatePanel,
  createClassroomClient,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  classroomQueryKeys,
  type InPersonEvent,
  type InPersonEventStatus,
  type SaveInPersonEventRequest,
} from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
} from '@vmsh/ui'

const MOSCOW_OFFSET_MS = 3 * 60 * 60 * 1000

interface EventDraft {
  name: string
  startsLocal: string
  endsLocal: string
  status: InPersonEventStatus
  groupLessonPublicIds: string[]
}

function toMoscowLocal(iso: string): string {
  return new Date(new Date(iso).getTime() + MOSCOW_OFFSET_MS).toISOString().slice(0, 16)
}

function toIso(local: string): string {
  return new Date(`${local}:00+03:00`).toISOString()
}

function initialDraft(event: InPersonEvent | undefined): EventDraft {
  if (event) {
    return {
      name: event.name,
      startsLocal: toMoscowLocal(event.startsAt),
      endsLocal: toMoscowLocal(event.endsAt),
      status: event.status,
      groupLessonPublicIds: event.groupLessons.map((group) => group.groupLessonPublicId),
    }
  }
  const start = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
  start.setUTCHours(7, 0, 0, 0)
  const end = new Date(start.getTime() + 3 * 60 * 60 * 1000)
  return {
    name: 'Очное занятие',
    startsLocal: toMoscowLocal(start.toISOString()),
    endsLocal: toMoscowLocal(end.toISOString()),
    status: 'draft',
    groupLessonPublicIds: [],
  }
}

function readDraft(key: string, fallback: EventDraft): EventDraft {
  try {
    const raw = globalThis.localStorage.getItem(key)
    if (!raw) return fallback
    const value = JSON.parse(raw) as Partial<EventDraft>
    if (
      typeof value.name !== 'string' ||
      typeof value.startsLocal !== 'string' ||
      typeof value.endsLocal !== 'string' ||
      !['draft', 'scheduled', 'completed', 'cancelled'].includes(value.status ?? '') ||
      !Array.isArray(value.groupLessonPublicIds) ||
      value.groupLessonPublicIds.some((id) => typeof id !== 'string')
    ) {
      return fallback
    }
    return value as EventDraft
  } catch {
    return fallback
  }
}

function describeError(error: Error): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof ClassroomNetworkError) return 'Проверьте соединение и повторите попытку.'
  return 'Обновите страницу и повторите попытку.'
}

function EventEditor({
  event,
  candidates,
  pending,
  onSave,
}: {
  event: InPersonEvent | undefined
  candidates: Array<{
    groupLessonPublicId: string
    courseName: string
    groupName: string
    shortCode: string
    lessonNumber: number
    inPersonCount: number
  }>
  pending: boolean
  onSave: (request: SaveInPersonEventRequest) => void
}) {
  const storageKey = `vmsh:staff:in-person-event:${event?.publicId ?? 'new'}`
  const [draft, setDraft] = useState(() => readDraft(storageKey, initialDraft(event)))
  const [storageFailed, setStorageFailed] = useState(false)

  const updateDraft = (next: EventDraft) => {
    setDraft(next)
    try {
      globalThis.localStorage.setItem(storageKey, JSON.stringify(next))
      setStorageFailed(false)
    } catch {
      setStorageFailed(true)
    }
  }

  const submit = (formEvent: FormEvent) => {
    formEvent.preventDefault()
    onSave({
      schemaVersion: 1,
      name: draft.name,
      startsAt: toIso(draft.startsLocal),
      endsAt: toIso(draft.endsLocal),
      status: draft.status,
      groupLessonPublicIds: draft.groupLessonPublicIds,
    })
  }

  return (
    <form className="grid gap-4" onSubmit={submit}>
      <div className="grid gap-3 md:grid-cols-4">
        <Label className="grid gap-1 md:col-span-2">
          Название
          <Input
            maxLength={200}
            onChange={(changeEvent) => updateDraft({ ...draft, name: changeEvent.target.value })}
            required
            value={draft.name}
          />
        </Label>
        <Label className="grid gap-1">
          Начало · Москва
          <Input
            onChange={(changeEvent) =>
              updateDraft({ ...draft, startsLocal: changeEvent.target.value })
            }
            required
            type="datetime-local"
            value={draft.startsLocal}
          />
        </Label>
        <Label className="grid gap-1">
          Окончание · Москва
          <Input
            onChange={(changeEvent) =>
              updateDraft({ ...draft, endsLocal: changeEvent.target.value })
            }
            required
            type="datetime-local"
            value={draft.endsLocal}
          />
        </Label>
      </div>
      <Label className="grid max-w-xs gap-1">
        Состояние
        <select
          className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
          onChange={(changeEvent) =>
            updateDraft({
              ...draft,
              status: changeEvent.target.value as InPersonEventStatus,
            })
          }
          value={draft.status}
        >
          <option value="draft">Черновик</option>
          <option value="scheduled">Объявлено</option>
          <option value="completed">Завершено</option>
          <option value="cancelled">Отменено</option>
        </select>
      </Label>
      <fieldset className="grid gap-2">
        <legend className="text-label font-medium">Какие группы участвуют</legend>
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {candidates.map((candidate) => {
            const checked = draft.groupLessonPublicIds.includes(candidate.groupLessonPublicId)
            return (
              <Label
                className="flex items-center gap-3 rounded-md border border-border bg-surface px-3 py-2"
                key={candidate.groupLessonPublicId}
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(next) =>
                    updateDraft({
                      ...draft,
                      groupLessonPublicIds:
                        next === true
                          ? [...draft.groupLessonPublicIds, candidate.groupLessonPublicId]
                          : draft.groupLessonPublicIds.filter(
                              (id) => id !== candidate.groupLessonPublicId,
                            ),
                    })
                  }
                />
                <span className="min-w-0 flex-1 text-small">
                  <span className="block font-medium">
                    {candidate.shortCode} · {candidate.groupName}
                  </span>
                  <span className="block text-caption text-muted-foreground">
                    {candidate.courseName} · занятие {candidate.lessonNumber} · очно{' '}
                    {candidate.inPersonCount}
                  </span>
                </span>
              </Label>
            )
          })}
        </div>
      </fieldset>
      {draft.status === 'scheduled' ? (
        <Alert tone="info">
          <CalendarClock aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Дата и время будут показаны школьникам и семьям</AlertTitle>
            <AlertDescription>
              Номер аудитории берётся только из подтверждённого плана. Уведомления отправляются
              отдельной рассылкой.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {storageFailed ? (
        <Alert tone="danger">
          <AlertContent>
            <AlertTitle>Черновик не сохранился на устройстве</AlertTitle>
          </AlertContent>
        </Alert>
      ) : null}
      <div>
        <Button
          disabled={
            pending ||
            draft.name.trim() === '' ||
            draft.groupLessonPublicIds.length === 0 ||
            draft.endsLocal <= draft.startsLocal
          }
          type="submit"
        >
          {event ? 'Сохранить очное занятие' : 'Создать очное занятие'}
        </Button>
      </div>
    </form>
  )
}

export function StaffClassroomEventManager({
  selectedEventPublicId,
  onEventChange,
}: {
  selectedEventPublicId: string | undefined
  onEventChange: (eventPublicId: string | undefined) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('In-person events require Staff auth')
  const queryClient = useQueryClient()
  const [creating, setCreating] = useState(false)
  const client = useMemo(
    () =>
      createClassroomClient(authentication.client.runtime, {
        refreshSession: async () => authentication.refresh(),
      }),
    [authentication],
  )
  const key = classroomQueryKeys.events(principal)
  const catalog = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => client.listInPersonEvents({ signal }),
    meta: { realtimeResources: ['in-person-events'] },
  })
  const selected = catalog.data?.events.find((event) => event.publicId === selectedEventPublicId)

  useEffect(() => {
    if (creating || !catalog.data) return
    if (selectedEventPublicId && selected) return
    onEventChange(catalog.data.events[0]?.publicId)
  }, [catalog.data, creating, onEventChange, selected, selectedEventPublicId])

  const mutation = useMutation({
    mutationFn: async (request: SaveInPersonEventRequest) =>
      selected
        ? client.updateInPersonEvent(selected, request)
        : client.createInPersonEvent(request),
    onSuccess: async (response) => {
      try {
        globalThis.localStorage.removeItem(
          `vmsh:staff:in-person-event:${selected?.publicId ?? 'new'}`,
        )
      } catch {
        // Saving to the server succeeded; stale local data is harmless.
      }
      setCreating(false)
      await queryClient.invalidateQueries({ queryKey: classroomQueryKeys.all(principal) })
      onEventChange(response.event.publicId)
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (catalog.isPending) return <PageStatePanel state="loading" />
  if (catalog.error) {
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>Не удалось загрузить очные занятия</AlertTitle>
          <AlertDescription>{describeError(catalog.error)}</AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <div>
          <CardTitle>Очное занятие</CardTitle>
          <p className="mt-1 text-caption text-muted-foreground">
            Выберите дату, время и конкретные занятия участвующих групп.
          </p>
        </div>
        <Button
          onClick={() => {
            setCreating(true)
            onEventChange(undefined)
          }}
          size="sm"
          type="button"
          variant="outline"
        >
          <Plus aria-hidden="true" /> Новое
        </Button>
      </CardHeader>
      <CardContent className="grid gap-4">
        {catalog.data.events.length > 0 && !creating ? (
          <Label className="grid max-w-xl gap-1">
            Событие
            <select
              className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
              onChange={(changeEvent) => onEventChange(changeEvent.target.value)}
              value={selected?.publicId ?? ''}
            >
              {catalog.data.events.map((event) => (
                <option key={event.publicId} value={event.publicId}>
                  {event.name} · {toMoscowLocal(event.startsAt).replace('T', ' ')}
                </option>
              ))}
            </select>
          </Label>
        ) : null}
        {selected ? <Badge variant="neutral">Версия {selected.version}</Badge> : null}
        <EventEditor
          candidates={catalog.data.candidates}
          event={selected}
          key={selected?.publicId ?? 'new'}
          onSave={(request) => mutation.mutate(request)}
          pending={mutation.isPending}
        />
        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Очное занятие не сохранено</AlertTitle>
              <AlertDescription>{describeError(mutation.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}
