import { plural, t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createProblemSynonymClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useProblemSynonymCandidatesQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  problemSynonymQueryKeys,
  type ProblemSynonymCandidatesResponse,
  type ProblemSynonymImpactResponse,
  type ProblemSynonymProblem,
} from '@vmsh/contracts'
import { SynonymMergeSplitPreview, answerTypeFromLegacyId, defaultAnswerHint } from '@vmsh/product'
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
  Input,
  Label,
  Textarea,
} from '@vmsh/ui'

const problemTypeLabel: Record<number, string> = {
  get 1() {
    return t`Тестовая`
  },
  get 2() {
    return t`Письменная`
  },
  get 3() {
    return t`Устная`
  },
  get 4() {
    return t`Устная с письменной сдачей`
  },
} as const

function taskNumber(problem: ProblemSynonymProblem): string {
  return `${problem.problemNumber}${problem.problemItem}`
}

function problemTypeText(value: number): string {
  return problemTypeLabel[value] ?? t`Тип ${value}`
}

function answerTypeText(value: number): string {
  return defaultAnswerHint(answerTypeFromLegacyId(value)).hint.replace(/^Введите /, '')
}

function countLabel(count: number, kind: 'problem' | 'submission' | 'review'): string {
  switch (kind) {
    case 'problem':
      return plural(count, { one: '# задача', few: '# задачи', many: '# задач', other: '# задачи' })
    case 'submission':
      return plural(count, {
        one: '# посылка',
        few: '# посылки',
        many: '# посылок',
        other: '# посылки',
      })
    case 'review':
      return plural(count, {
        one: '# проверка',
        few: '# проверки',
        many: '# проверок',
        other: '# проверки',
      })
  }
}

function previewProblem(problem: ProblemSynonymProblem) {
  return {
    problemId: problem.problemId,
    courseName: problem.courseName,
    groupName: problem.groupName,
    lessonNumber: problem.lessonNumber,
    taskNumber: taskNumber(problem),
    title: problem.title,
    taskType: problemTypeText(problem.problemType),
    ...(problem.answerType === null ? {} : { answerType: answerTypeText(problem.answerType) }),
    submissionCount: problem.submissionCount,
    reviewCount: problem.reviewCount,
  }
}

function errorMessage(error: Error): string {
  return error instanceof ApiResponseError
    ? error.message
    : t`Не удалось выполнить операцию. Обновите данные и попробуйте ещё раз.`
}

export function ProblemSynonymView({
  data,
  error,
  pending,
  preview,
  onCancelPreview,
  onConfirm,
  onPreviewMerge,
  onPreviewSplit,
}: {
  data: ProblemSynonymCandidatesResponse
  error?: Error
  pending: boolean
  preview?: ProblemSynonymImpactResponse
  onCancelPreview: () => void
  onConfirm: (preview: ProblemSynonymImpactResponse, reason: string) => void
  onPreviewMerge: (problemIds: string[]) => void
  onPreviewSplit: (synonymId: string, problemIds: string[]) => void
}) {
  const [splitReason, setSplitReason] = useState('')

  return (
    <div className="space-y-5">
      {error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>
              <Trans>Изменение не выполнено</Trans>
            </AlertTitle>
            <AlertDescription>{errorMessage(error)}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {preview ? (
        <Card>
          <CardHeader>
            <CardTitle>
              <Trans>Предпросмотр влияния</Trans>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SynonymMergeSplitPreview
              confirmDisabled={pending || (preview.mode === 'split' && !splitReason.trim())}
              mode={preview.mode}
              onCancel={() => {
                setSplitReason('')
                onCancelPreview()
              }}
              onConfirm={() => onConfirm(preview, splitReason)}
              problems={preview.problems.map(previewProblem)}
            />
            {preview.mode === 'split' ? (
              <Label className="grid max-w-2xl gap-1 text-small">
                <Trans>Причина разделения</Trans>
                <Textarea
                  disabled={pending}
                  maxLength={500}
                  onChange={(event) => setSplitReason(event.target.value)}
                  placeholder={t`Например: задачи были объединены по совпавшему названию`}
                  value={splitReason}
                />
              </Label>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <section aria-labelledby="synonym-candidates-title" className="space-y-3">
        <div>
          <h2 className="text-subtitle font-semibold" id="synonym-candidates-title">
            <Trans>Кандидаты · {data.candidates.length}</Trans>
          </h2>
          <p className="text-small text-muted-foreground">
            <Trans>
              Совпавшее название только предлагает связь. Объединение всегда требует предпросмотра и
              подтверждения администратора.
            </Trans>
          </p>
        </div>
        {data.candidates.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-4 text-small text-muted-foreground">
            <Trans>Неподтверждённых совпадений на этом занятии нет.</Trans>
          </p>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {data.candidates.map((candidate) => (
              <Card key={candidate.normalizedTitle}>
                <CardHeader className="gap-2 pb-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <CardTitle>{candidate.displayTitle}</CardTitle>
                    <Badge variant={candidate.hasGroupConflict ? 'warning' : 'neutral'}>
                      {countLabel(candidate.problems.length, 'problem')}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <ul className="divide-y divide-border rounded-md border border-border">
                    {candidate.problems.map((problem) => (
                      <li
                        className="flex items-center justify-between gap-3 px-3 py-2"
                        key={problem.problemId}
                      >
                        <span className="min-w-0">
                          <span className="block text-small font-medium">
                            <Trans>{problem.groupCode} · задача</Trans> {taskNumber(problem)}
                          </span>
                          <span className="block text-caption text-muted-foreground">
                            {problemTypeText(problem.problemType)} ·{' '}
                            {countLabel(problem.submissionCount, 'submission')} ·{' '}
                            {countLabel(problem.reviewCount, 'review')}
                          </span>
                        </span>
                        <Badge variant="neutral">{problem.groupName}</Badge>
                      </li>
                    ))}
                  </ul>
                  {candidate.hasGroupConflict ? (
                    <Alert tone="warning">
                      <AlertContent>
                        <AlertTitle>
                          <Trans>В одной группе найдено несколько задач</Trans>
                        </AlertTitle>
                        <AlertDescription>
                          <Trans>
                            Сначала исправьте повтор в метаданных: одна группа занятия может
                            содержать только один экземпляр синонимичной задачи.
                          </Trans>
                        </AlertDescription>
                      </AlertContent>
                    </Alert>
                  ) : (
                    <Button
                      disabled={pending || preview !== undefined}
                      onClick={() =>
                        onPreviewMerge(candidate.problems.map((problem) => problem.problemId))
                      }
                      size="sm"
                      variant="outline"
                    >
                      <Trans>Проверить объединение</Trans>
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="active-synonyms-title" className="space-y-3">
        <div>
          <h2 className="text-subtitle font-semibold" id="active-synonyms-title">
            <Trans>Подтверждённые связи · {data.synonymGroups.length}</Trans>
          </h2>
          <p className="text-small text-muted-foreground">
            <Trans>
              Исходные посылки и проверки не переносятся. Если связь ошибочна, отделите конкретную
              задачу после предпросмотра.
            </Trans>
          </p>
        </div>
        {data.synonymGroups.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-4 text-small text-muted-foreground">
            <Trans>Подтверждённых связей на этом занятии пока нет.</Trans>
          </p>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {data.synonymGroups.map((group) => (
              <Card key={group.synonymId}>
                <CardHeader className="gap-1 pb-3">
                  <CardTitle>{group.displayTitle}</CardTitle>
                  <p className="font-num text-caption text-muted-foreground">
                    <Trans>версия {group.version}</Trans>
                  </p>
                </CardHeader>
                <CardContent>
                  <ul className="divide-y divide-border rounded-md border border-border">
                    {group.problems.map((problem) => (
                      <li
                        className="flex items-center justify-between gap-3 px-3 py-2"
                        key={problem.problemId}
                      >
                        <span className="min-w-0 text-small">
                          <span className="font-medium">{problem.groupName}</span>
                          <span className="text-muted-foreground">
                            <Trans> · задача</Trans> {taskNumber(problem)}
                          </span>
                        </span>
                        <Button
                          disabled={pending || preview !== undefined}
                          onClick={() => onPreviewSplit(group.synonymId, [problem.problemId])}
                          size="sm"
                          variant="ghost"
                        >
                          <Trans>Отделить</Trans>
                        </Button>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export function ProblemSynonymPage({
  courseLessonId,
  onCourseLessonChange,
}: {
  courseLessonId?: string
  onCourseLessonChange: (courseLessonId: string) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Problem synonyms require Staff auth')
  const isAdmin = principal.role === 'admin'
  const client = useMemo(
    () =>
      createProblemSynonymClient(authentication.client.runtime, {
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
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const query = useProblemSynonymCandidatesQuery(
    client,
    scope,
    courseLessonId ?? 'course-lesson-not-selected',
    isAdmin && courseLessonId !== undefined,
  )
  const preview = useMutation({
    mutationFn: (request: Parameters<typeof client.preview>[0]) => client.preview(request),
    onError: (error) => authentication.handleApiError(error),
  })
  const apply = useMutation({
    mutationFn: async ({
      impact,
      reason,
    }: {
      impact: ProblemSynonymImpactResponse
      reason: string
    }) => {
      if (impact.mode === 'merge') {
        return client.merge({
          schemaVersion: 1,
          problemIds: impact.selectedProblemIds,
          previewSha256: impact.previewSha256,
        })
      }
      if (impact.synonym === null) throw new Error('Split preview has no synonym')
      return client.split(impact.synonym.synonymId, {
        schemaVersion: 1,
        problemIds: impact.selectedProblemIds,
        previewSha256: impact.previewSha256,
        reason,
      })
    },
    onError: (error) => authentication.handleApiError(error),
    onSuccess: async () => {
      preview.reset()
      await queryClient.invalidateQueries({ queryKey: problemSynonymQueryKeys.all(scope) })
    },
  })

  if (!isAdmin) {
    return (
      <PageLayout title={t`Синонимы задач`} width="wide">
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }

  if (!courseLessonId) {
    return <CourseLessonSelector onSelect={onCourseLessonChange} />
  }

  if (query.isPending) {
    return (
      <PageLayout title={t`Синонимы задач`} width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (query.error || !query.data) {
    return (
      <PageLayout title={t`Синонимы задач`} width="wide">
        <PageStatePanel
          actionLabel={t`Повторить`}
          onAction={() => void query.refetch()}
          state="error"
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description={t`Связи меняют только вычисляемое представление. Каждая посылка, переписка и проверка остаётся у исходной задачи.`}
      eyebrow={t`Занятие курса · ${courseLessonId}`}
      title={t`Синонимы задач`}
      width="wide"
    >
      <ProblemSynonymView
        data={query.data}
        {...(preview.error || apply.error ? { error: (apply.error ?? preview.error)! } : {})}
        onCancelPreview={() => preview.reset()}
        onConfirm={(impact, reason) => apply.mutate({ impact, reason })}
        onPreviewMerge={(problemIds) => {
          apply.reset()
          preview.mutate({ schemaVersion: 1, mode: 'merge', problemIds, synonymId: null })
        }}
        onPreviewSplit={(synonymId, problemIds) => {
          apply.reset()
          preview.mutate({ schemaVersion: 1, mode: 'split', problemIds, synonymId })
        }}
        pending={preview.isPending || apply.isPending}
        {...(preview.data ? { preview: preview.data } : {})}
      />
    </PageLayout>
  )
}

function CourseLessonSelector({ onSelect }: { onSelect: (courseLessonId: string) => void }) {
  const [value, setValue] = useState('')
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (value.trim()) onSelect(value.trim())
  }
  return (
    <PageLayout
      description={t`Откройте этот раздел из конкретного занятия или укажите его публичный идентификатор.`}
      eyebrow="Admin"
      title={t`Синонимы задач`}
      width="content"
    >
      <Card>
        <CardContent className="pt-4">
          <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={submit}>
            <Label className="grid min-w-0 flex-1 gap-1 text-small">
              <Trans>Идентификатор занятия курса</Trans>
              <Input
                onChange={(event) => setValue(event.target.value)}
                placeholder="course-lesson…"
                required
                value={value}
              />
            </Label>
            <Button type="submit">
              <Trans>Открыть</Trans>
            </Button>
          </form>
        </CardContent>
      </Card>
    </PageLayout>
  )
}
