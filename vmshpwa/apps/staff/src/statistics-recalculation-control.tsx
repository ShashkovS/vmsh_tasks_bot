import { useEffect, useMemo, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createStatisticsRecalculationClient,
  useAuthentication,
  useAuthenticatedPrincipal,
} from '@vmsh/app-shell'
import { createBrowserStorageNamespace } from '@vmsh/contracts'
import { Button } from '@vmsh/ui'

/** Durable course operation; docs/lesson-statistics.md. No lesson/group filter affects training. */
export function StatisticsRecalculationControl({
  courseId,
  onRefresh,
}: {
  courseId: string
  onRefresh: () => void
}) {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () => createStatisticsRecalculationClient(auth.client.runtime, () => auth.refresh()),
    [auth],
  )
  const queryClient = useQueryClient()
  const queryKey = ['statistics-recalculation', principal.accountId, courseId]
  const storageKey = `${createBrowserStorageNamespace(auth.client.runtime)}:${principal.accountId}:recalculate:${courseId}`
  const status = useQuery({
    queryKey,
    queryFn: () => client(courseId),
    refetchOnWindowFocus: 'always',
    refetchInterval: (query) => (query.state.data?.busy ? 1500 : false),
  })
  const mutation = useMutation({
    mutationFn: () => {
      const key = window.localStorage.getItem(storageKey) ?? crypto.randomUUID()
      window.localStorage.setItem(storageKey, key)
      return client(courseId, key)
    },
    onSuccess: (data) => {
      window.localStorage.removeItem(storageKey)
      queryClient.setQueryData(queryKey, data)
      void queryClient.invalidateQueries({ queryKey })
    },
    onError: (error) => auth.handleApiError(error),
  })
  const operation = status.data?.operation
  const refreshed = useRef<string | null>(null)
  useEffect(() => {
    if (operation?.runId && operation.runId !== refreshed.current) {
      refreshed.current = operation.runId
      onRefresh()
    }
  }, [operation?.runId, onRefresh])
  const busy = mutation.isPending || status.data?.busy
  return (
    <div className="space-y-1">
      <Button
        disabled={Boolean(busy) || status.isPending}
        onClick={() => mutation.mutate()}
        variant="outline"
      >
        {busy ? 'Пересчитываем…' : 'Пересчитать сложность'}
      </Button>
      <p className="text-caption text-muted-foreground">Пересчёт сложности и силы по всему курсу</p>
      <p className="text-caption text-muted-foreground" role="status">
        {busy
          ? 'Расчёт уже выполняется. Можно покинуть страницу.'
          : mutation.error
            ? 'Не удалось подтвердить запуск. Повторите запрос.'
            : status.error
              ? 'Не удалось загрузить состояние пересчёта. Попробуйте ещё раз.'
              : operation?.state === 'failed'
                ? 'Пересчёт не завершён. Прежние показатели сохранены. Можно повторить.'
                : operation?.state === 'completed' && operation.completedAt
                  ? `Пересчитано: ${new Date(operation.completedAt).toLocaleString('ru-RU')}`
                  : null}
      </p>
    </div>
  )
}
