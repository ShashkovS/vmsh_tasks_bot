import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

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
  type Classroom,
  type ClassroomListStatus,
} from '@vmsh/contracts'
import {
  ClassroomCatalog,
  type ClassroomCatalogRoom,
  type ClassroomNameConflict,
} from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

type CatalogMutation =
  | { kind: 'create'; name: string }
  | { kind: 'rename'; room: Classroom; name: string }
  | { kind: 'archive'; room: Classroom }
  | { kind: 'restore'; room: Classroom }

function describeClassroomError(error: Error): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof ClassroomNetworkError) return 'Проверьте соединение и повторите попытку.'
  return 'Обновите страницу и повторите попытку.'
}

/** Real catalog tab for Phase 7; the other classroom tabs remain prototypes. */
export function StaffClassroomCatalog({
  statusFilter,
  onStatusFilterChange,
}: {
  statusFilter: ClassroomListStatus
  onStatusFilterChange: (status: ClassroomListStatus) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Classroom catalog requires Staff auth')
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [newRoomName, setNewRoomName] = useState('')
  const [conflict, setConflict] = useState<ClassroomNameConflict | null>(null)
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
  const listKey = classroomQueryKeys.list(principal, { status: 'all', search: '' })
  const catalog = useQuery({
    queryKey: listKey,
    queryFn: ({ signal }) => client.list({ status: 'all' }, { signal }),
    meta: { realtimeResources: ['classrooms'] },
  })
  const mutation = useMutation({
    mutationFn: async (command: CatalogMutation) => {
      if (command.kind === 'create') {
        return client.create({ schemaVersion: 1, name: command.name })
      }
      if (command.kind === 'rename') {
        return client.rename(command.room, { schemaVersion: 1, name: command.name })
      }
      if (command.kind === 'archive') {
        return client.archive(command.room, { schemaVersion: 1 })
      }
      return client.restore(command.room, { schemaVersion: 1 })
    },
    onMutate: () => setConflict(null),
    onSuccess: async (_, command) => {
      if (command.kind === 'create') setNewRoomName('')
      await queryClient.invalidateQueries({ queryKey: classroomQueryKeys.all(principal) })
    },
    onError: (error, command) => {
      authentication.handleApiError(error)
      if (error instanceof ApiResponseError && error.code === 'classroom_name_conflict') {
        const existingRoomId = error.details?.existingPublicId
        const existingRoomName = error.details?.existingName
        if (typeof existingRoomId === 'string' && typeof existingRoomName === 'string') {
          setConflict({
            inputName: command.kind === 'archive' || command.kind === 'restore' ? '' : command.name,
            existingRoomId,
            existingRoomName,
          })
        }
      }
    },
  })

  if (catalog.isPending) return <PageStatePanel state="loading" />
  if (catalog.error) {
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>
            {catalog.error instanceof ApiResponseError && catalog.error.status === 403
              ? 'Недостаточно прав'
              : catalog.error instanceof ClassroomNetworkError
                ? 'Нет соединения'
                : 'Не удалось загрузить каталог'}
          </AlertTitle>
          <AlertDescription>{describeClassroomError(catalog.error)}</AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  const roomsById = new Map(catalog.data.items.map((room) => [room.publicId, room]))
  const rooms: ClassroomCatalogRoom[] = catalog.data.items.map((room) => ({
    id: room.publicId,
    name: room.name,
    status: room.status,
    version: room.version,
  }))
  const runForRoom = (kind: 'archive' | 'restore', roomId: string) => {
    const room = roomsById.get(roomId)
    if (room) mutation.mutate({ kind, room })
  }
  const pendingRoomId =
    mutation.isPending && mutation.variables.kind !== 'create'
      ? mutation.variables.room.publicId
      : null

  return (
    <div className="space-y-3">
      {mutation.error && !conflict ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Изменение не сохранено</AlertTitle>
            <AlertDescription>{describeClassroomError(mutation.error)}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      <ClassroomCatalog
        conflict={conflict}
        newRoomName={newRoomName}
        onArchive={(roomId) => runForRoom('archive', roomId)}
        onCreate={(name) => {
          if (!mutation.isPending) mutation.mutate({ kind: 'create', name })
        }}
        onNewRoomNameChange={setNewRoomName}
        onQueryChange={setQuery}
        onRename={(roomId, name) => {
          const room = roomsById.get(roomId)
          if (room) mutation.mutate({ kind: 'rename', room, name })
        }}
        onRestore={(roomId) => runForRoom('restore', roomId)}
        onRevealConflict={() => {
          if (!conflict) return
          onStatusFilterChange('all')
          setQuery(conflict.existingRoomName)
        }}
        onStatusFilterChange={onStatusFilterChange}
        pendingRoomId={pendingRoomId}
        query={query}
        rooms={rooms}
        statusFilter={statusFilter}
      />
    </div>
  )
}
