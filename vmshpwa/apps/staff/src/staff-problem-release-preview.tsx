import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useAuthentication } from '@vmsh/app-shell'
import { Button, Switch } from '@vmsh/ui'
import type { ProblemReleaseRequest } from '@vmsh/contracts'
import { createProblemReleaseClient, type ProblemReleaseClient } from './problem-release-client'
import { StaffWorksheetPreview } from './staff-worksheet-preview'
import type { ComponentProps } from 'react'

type PreviewProps = ComponentProps<typeof StaffWorksheetPreview>

export function StaffProblemReleasePreview(
  props: PreviewProps & { groupLessonId: string; revisionId: string },
) {
  const authentication = useAuthentication()
  const client = useMemo(
    () => createProblemReleaseClient(authentication.client.runtime, () => authentication.refresh()),
    [authentication],
  )
  return <ProblemReleasePreview {...props} client={client} />
}

/** Authoritative Query state, no optimistic hiding; docs/problem-release.md. */
export function ProblemReleasePreview({
  client,
  groupLessonId,
  revisionId,
  ...preview
}: PreviewProps & {
  client: ProblemReleaseClient
  groupLessonId: string
  revisionId: string
}) {
  const queryClient = useQueryClient()
  const queryKey = ['staff-problem-release', groupLessonId, revisionId]
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => client.get(groupLessonId, revisionId, signal),
    meta: {
      realtimeResources: [
        `group-lessons/${groupLessonId}/problem-release`,
        `group-lessons/${groupLessonId}/content/condition`,
      ],
    },
  })
  const mutation = useMutation({
    mutationFn: (changes: ProblemReleaseRequest['changes']) =>
      client.save(groupLessonId, query.data!.etag, { conditionRevisionId: revisionId, changes }),
    onSuccess: (data) => queryClient.setQueryData(queryKey, data),
    onError: () => {
      void query.refetch()
    },
  })
  const data = query.data
  const disabled = mutation.isPending || !data?.editable
  const openCount = data?.problems.filter((problem) => problem.isOpen).length ?? 0
  const saveAll = (isOpen: boolean) => {
    if (!disabled && data?.problems.length)
      mutation.mutate(
        data.problems.map((problem) => ({ sourceOrdinal: problem.sourceOrdinal, isOpen })),
      )
  }
  return (
    <>
      <section aria-label={t`Позадачная публикация`} className="mb-3 space-y-2 font-sans">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">
            <Trans>Позадачная публикация</Trans>
          </span>
          {data ? (
            <span role="status" className="text-small text-muted-foreground">
              <Trans>
                Открыто {openCount} из {data.problems.length}
              </Trans>
            </span>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || !data?.problems.length || openCount === 0}
            onClick={() => saveAll(false)}
          >
            <Trans>Закрыть все</Trans>
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={disabled || !data?.problems.length || openCount === data.problems.length}
            onClick={() => saveAll(true)}
          >
            <Trans>Открыть все</Trans>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={query.isFetching || mutation.isPending}
            onClick={() => void query.refetch()}
          >
            <Trans>Обновить переключатели</Trans>
          </Button>
        </div>
        {data && !data.editable ? (
          <p className="text-small text-muted-foreground">
            <Trans>
              Прогноз для выбранной версии. Переключать задачи можно в текущем опубликованном
              листке.
            </Trans>
          </p>
        ) : null}
        {data && !data.problems.length ? (
          <p className="text-small text-muted-foreground">
            <Trans>
              Сначала сохраните сопоставление и метаданные задач, затем обновите переключатели.
            </Trans>
          </p>
        ) : null}
        {query.isPending ? (
          <p role="status">
            <Trans>Загружаем переключатели…</Trans>
          </p>
        ) : null}
        {mutation.isError || query.isError ? (
          <p role="alert" className="text-small text-destructive">
            <Trans>
              Не удалось сохранить или загрузить доступность задач. Обновите переключатели и
              повторите действие.
            </Trans>
          </p>
        ) : null}
      </section>
      <StaffWorksheetPreview
        {...preview}
        renderReleaseControl={(problem) => {
          const state = data?.problems.find((item) => item.sourceOrdinal === problem.ordinal)
          return state ? (
            <span className="inline-flex items-center gap-2 font-sans text-small">
              <Switch
                size="sm"
                checked={state.isOpen}
                disabled={disabled}
                aria-label={t`Открыта ученикам: задача ${problem.taskReference ?? problem.ordinal}`}
                onCheckedChange={(isOpen) => {
                  if (!disabled) mutation.mutate([{ sourceOrdinal: problem.ordinal, isOpen }])
                }}
              />
              <Trans>Открыта ученикам</Trans>
            </span>
          ) : null
        }}
      />
    </>
  )
}
