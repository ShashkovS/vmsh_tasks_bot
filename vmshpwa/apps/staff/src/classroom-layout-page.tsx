import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  ClassroomNetworkError,
  PageStatePanel,
  createClassroomClient,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import { ApiResponseError, classroomQueryKeys, type ClassroomLayout } from '@vmsh/contracts'
import {
  ClassroomGroupLayout,
  type ClassroomGroupOption,
  type ClassroomLayoutRoom,
} from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

function colorIndex(colorKey: string | null): 0 | 1 | 2 | 3 | 4 {
  const match = /^level-([1-4])$/.exec(colorKey ?? '')
  return match ? (Number(match[1]) as 1 | 2 | 3 | 4) : 0
}

function describeError(error: Error): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof ClassroomNetworkError) return 'Проверьте соединение и повторите попытку.'
  return 'Обновите страницу и повторите попытку.'
}

function defaultMappings(layout: ClassroomLayout): Record<string, string | null> {
  return Object.fromEntries(
    layout.rooms.map((room) => [room.classroomPublicId, room.groupLessonPublicId]),
  )
}

function readSavedMappings(storageKey: string): {
  mappings: Record<string, string | null>
  publicId: string | null
  version: number | null
} | null {
  try {
    const raw = globalThis.localStorage.getItem(storageKey)
    if (raw === null) return null
    const value: unknown = JSON.parse(raw)
    if (typeof value !== 'object' || value === null || !('mappings' in value)) return null
    const candidate = value as Record<string, unknown>
    if (typeof candidate.mappings !== 'object' || candidate.mappings === null) return null
    const mappings: Record<string, string | null> = {}
    const rawMappings = candidate.mappings as Record<string, unknown>
    for (const [roomId, groupId] of Object.entries(rawMappings)) {
      if (typeof groupId === 'string' || groupId === null) mappings[roomId] = groupId
    }
    return {
      mappings,
      publicId: typeof candidate.publicId === 'string' ? candidate.publicId : null,
      version: typeof candidate.version === 'number' ? candidate.version : null,
    }
  } catch {
    return null
  }
}

function LayoutEditor({
  eventPublicId,
  layout,
  catalog,
  client,
  storageKey,
  onChanged,
}: {
  eventPublicId: string
  layout: ClassroomLayout
  catalog: Array<{ publicId: string; name: string; status: 'active' | 'archived' }>
  client: ReturnType<typeof createClassroomClient>
  storageKey: string
  onChanged: () => Promise<void>
}) {
  const authentication = useAuthentication()
  const saved = useMemo(() => readSavedMappings(storageKey), [storageKey])
  const [mappings, setMappings] = useState<Record<string, string | null>>(
    saved?.mappings ?? defaultMappings(layout),
  )
  const [dirty, setDirty] = useState(saved !== null)
  const [draftBase, setDraftBase] = useState(
    saved === null ? null : { publicId: saved.publicId, version: saved.version },
  )
  const [storageFailed, setStorageFailed] = useState(false)

  const groups: ClassroomGroupOption[] = layout.groups.map((group) => ({
    id: group.groupLessonPublicId,
    name: `${group.courseName} · ${group.groupName}`,
    shortCode: group.shortCode,
    colorIndex: colorIndex(group.colorKey),
    inPersonCount: group.inPersonCount,
    assignedCount: group.assignedCount,
  }))
  const rooms: ClassroomLayoutRoom[] = catalog.map((room) => ({
    id: room.publicId,
    name: room.name,
    groupId: mappings[room.publicId] ?? null,
    invalid: room.status === 'archived' && typeof mappings[room.publicId] === 'string',
  }))

  const mutation = useMutation({
    mutationFn: async (kind: 'materialize' | 'confirm') => {
      if (kind === 'materialize') {
        return client.materializeLayout(eventPublicId, { schemaVersion: 1 })
      }
      if (layout.publicId === null || layout.version === null || layout.state !== 'draft') {
        throw new Error('Only a persisted draft can be confirmed')
      }
      const updated = await client.replaceLayout(
        eventPublicId,
        { publicId: layout.publicId, version: layout.version },
        {
          schemaVersion: 1,
          mappings: Object.entries(mappings).flatMap(([classroomPublicId, groupLessonPublicId]) =>
            groupLessonPublicId === null ? [] : [{ classroomPublicId, groupLessonPublicId }],
          ),
        },
      )
      if (updated.layout.publicId === null || updated.layout.version === null) {
        throw new Error('Server returned a virtual layout after saving a draft')
      }
      return client.confirmLayout(
        eventPublicId,
        { publicId: updated.layout.publicId, version: updated.layout.version },
        { schemaVersion: 1 },
      )
    },
    onSuccess: async (_, kind) => {
      if (kind === 'confirm') {
        try {
          globalThis.localStorage.removeItem(storageKey)
        } catch {
          setStorageFailed(true)
        }
        setDirty(false)
        setDraftBase(null)
      }
      await onChanged()
    },
    onError: async (error) => {
      authentication.handleApiError(error)
      await onChanged()
    },
  })

  const saveLocal = (next: Record<string, string | null>) => {
    setMappings(next)
    if (!dirty) setDraftBase({ publicId: layout.publicId, version: layout.version })
    setDirty(true)
    try {
      globalThis.localStorage.setItem(
        storageKey,
        JSON.stringify({ publicId: layout.publicId, version: layout.version, mappings: next }),
      )
      setStorageFailed(false)
    } catch {
      setStorageFailed(true)
    }
  }
  const savedAgainstAnotherVersion =
    dirty &&
    draftBase !== null &&
    (draftBase.publicId !== layout.publicId || draftBase.version !== layout.version)

  return (
    <div className="space-y-3">
      {storageFailed ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Локальный черновик не сохранён</AlertTitle>
            <AlertDescription>Не закрывайте страницу до подтверждения схемы.</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {layout.conflicts.length > 0 ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Одна аудитория унаследована несколькими группами</AlertTitle>
            <AlertDescription>
              {layout.conflicts.map((conflict) => conflict.classroomName).join(', ')} не попадёт в
              черновик, пока администратор не выберет группу заново.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {mutation.error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Схема не сохранена</AlertTitle>
            <AlertDescription>{describeError(mutation.error)}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      <ClassroomGroupLayout
        groups={groups}
        lessonLabel={`${layout.event.name} · ${new Date(layout.event.startsAt).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })}`}
        onConfirm={() => mutation.mutate('confirm')}
        onMaterialize={() => mutation.mutate('materialize')}
        onRoomGroupChange={(roomId, groupId) => saveLocal({ ...mappings, [roomId]: groupId })}
        optimisticConflict={
          savedAgainstAnotherVersion
            ? 'На устройстве есть изменения от другой версии. Они сохранены; сравните схему перед подтверждением.'
            : null
        }
        pending={mutation.isPending}
        rooms={rooms}
        {...(layout.state === 'inherited'
          ? { sourceLabel: 'из последних подтверждённых событий групп' }
          : {})}
        state={layout.state}
        version={layout.version}
      />
    </div>
  )
}

/** Live room-to-group tab; Student assignments remain a later Phase-7 slice. */
export function StaffClassroomLayout({ eventPublicId }: { eventPublicId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Classroom layout requires Staff auth')
  const queryClient = useQueryClient()
  const client = useMemo(
    () =>
      createClassroomClient(authentication.client.runtime, {
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
  const layoutKey = classroomQueryKeys.layout(principal, eventPublicId)
  const layoutQuery = useQuery({
    queryKey: layoutKey,
    queryFn: ({ signal }) => client.getLayout(eventPublicId, { signal }),
    meta: { realtimeResources: ['classroom-layouts'] },
  })
  const catalogQuery = useQuery({
    queryKey: classroomQueryKeys.list(principal, { status: 'all' }),
    queryFn: ({ signal }) => client.list({ status: 'all' }, { signal }),
    meta: { realtimeResources: ['classrooms'] },
  })

  if (layoutQuery.isPending || catalogQuery.isPending) return <PageStatePanel state="loading" />
  const error = layoutQuery.error ?? catalogQuery.error
  if (error) {
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>
            {error instanceof ApiResponseError && error.status === 403
              ? 'Недостаточно прав'
              : 'Не удалось загрузить схему'}
          </AlertTitle>
          <AlertDescription>{describeError(error)}</AlertDescription>
        </AlertContent>
      </Alert>
    )
  }
  if (layoutQuery.data === undefined || catalogQuery.data === undefined) {
    return <PageStatePanel state="error" />
  }

  return (
    <LayoutEditor
      catalog={catalogQuery.data.items}
      client={client}
      eventPublicId={eventPublicId}
      key={`${eventPublicId}:${layoutQuery.data.layout.publicId ?? 'inherited'}:${layoutQuery.data.layout.version ?? 0}`}
      layout={layoutQuery.data.layout}
      onChanged={async () => {
        await queryClient.invalidateQueries({ queryKey: layoutKey })
      }}
      storageKey={`vmsh-179:classroom-layout:${authentication.client.runtime.instance}:${principal.accountId}:${eventPublicId}`}
    />
  )
}
