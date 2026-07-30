import { useMutation } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  useAdminCourseCatalogQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type AdminCourse,
  type ProblemImportAction,
  type ProblemImportPreviewResponse,
  type ProblemImportReceipt,
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
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@vmsh/ui'

const actionLabels: Record<ProblemImportAction, string> = {
  create: 'Новая',
  update: 'Изменится',
  unchanged: 'Без изменений',
  invalid: 'Ошибка',
}

function actionBadge(action: ProblemImportAction) {
  const variant =
    action === 'invalid'
      ? 'danger'
      : action === 'create'
        ? 'success'
        : action === 'update'
          ? 'warning'
          : 'neutral'
  return <Badge variant={variant}>{actionLabels[action]}</Badge>
}

function identity(row: ProblemImportPreviewResponse['rows'][number]): string {
  return `${row.groupCode ?? '—'} · ${row.lessonNumber ?? '—'}.${row.problemNumber ?? '—'}${row.item}`
}

export function ProblemImportView({
  courses,
  error,
  pending,
  preview,
  receipt,
  reviewedWorkbook,
  onApply,
  onPreview,
  onRollback,
}: {
  courses: AdminCourse[]
  error?: Error
  pending: boolean
  preview?: ProblemImportPreviewResponse
  receipt?: ProblemImportReceipt
  reviewedWorkbook?: File
  onApply: (courseId: string, workbook: File, preview: ProblemImportPreviewResponse) => void
  onPreview: (courseId: string, workbook: File) => void
  onRollback: (receipt: ProblemImportReceipt) => void
}) {
  const [courseId, setCourseId] = useState(
    courses.find((course) => course.status === 'active')?.courseId ?? courses[0]?.courseId ?? '',
  )
  const [workbook, setWorkbook] = useState<File>()
  const [filter, setFilter] = useState<'changes' | ProblemImportAction>('changes')
  const [confirmation, setConfirmation] = useState<'apply' | 'rollback' | null>(null)
  const filteredRows = useMemo(() => {
    if (!preview) return []
    if (filter === 'changes') return preview.rows.filter((row) => row.action !== 'unchanged')
    return preview.rows.filter((row) => row.action === filter)
  }, [filter, preview])
  const visibleRows = filteredRows.slice(0, 300)
  const changedRows = preview ? preview.summary.create + preview.summary.update : 0
  const selectionMatchesPreview =
    preview !== undefined &&
    receipt === undefined &&
    workbook === reviewedWorkbook &&
    courseId === preview.course.courseId

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (courseId && workbook) {
      setConfirmation(null)
      onPreview(courseId, workbook)
    }
  }

  return (
    <div className="space-y-5">
      <Alert>
        <AlertContent>
          <AlertTitle>Сначала только проверка</AlertTitle>
          <AlertDescription>
            Предпросмотр читает листы «Задачи» и «Старые» и сравнивает их с SQLite, но ничего не
            сохраняет.
          </AlertDescription>
        </AlertContent>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>Файл и курс</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 md:grid-cols-[minmax(14rem,22rem)_minmax(18rem,1fr)_auto] md:items-end"
            onSubmit={submit}
          >
            <Label className="grid gap-1 text-small">
              Курс
              <select
                className="h-10 rounded-md border border-input bg-surface px-3 text-small"
                disabled={pending}
                onChange={(event) => {
                  setCourseId(event.target.value)
                  setConfirmation(null)
                }}
                value={courseId}
              >
                {courses.map((course) => (
                  <option key={course.courseId} value={course.courseId}>
                    {course.name} · {course.code}
                  </option>
                ))}
              </select>
            </Label>
            <Label className="grid gap-1 text-small">
              XLSX-файл
              <Input
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                disabled={pending}
                onChange={(event) => {
                  setWorkbook(event.target.files?.[0])
                  setConfirmation(null)
                }}
                type="file"
              />
            </Label>
            <Button disabled={!courseId || !workbook || pending} type="submit">
              {pending ? 'Проверяем…' : 'Проверить файл'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Операция не выполнена</AlertTitle>
            <AlertDescription>
              {error instanceof ApiResponseError
                ? error.message
                : 'Не удалось проверить файл. Повторите попытку.'}
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {preview ? (
        <section aria-labelledby="problem-import-result" className="space-y-4">
          <div>
            <h2 className="text-title font-semibold" id="problem-import-result">
              Результат проверки
            </h2>
            <p className="text-small text-muted-foreground">
              {preview.source.filename} · {preview.course.name}
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
            {(
              [
                ['Строк', preview.summary.rows],
                ['Новых', preview.summary.create],
                ['Изменятся', preview.summary.update],
                ['Без изменений', preview.summary.unchanged],
                ['С ошибками', preview.summary.invalid],
              ] as const
            ).map(([label, value]) => (
              <Card key={label}>
                <CardContent className="py-3">
                  <p className="text-caption text-muted-foreground">{label}</p>
                  <p className="font-num text-title font-semibold">{value}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          {preview.synonymCandidates.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Возможные синонимы · {preview.synonymCandidates.length}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-small text-muted-foreground">
                  Одинаковые названия найдены в разных группах одного занятия. Импорт не объединяет
                  задачи автоматически: каждую связь нужно подтвердить отдельно.
                </p>
                <ul className="grid gap-2 lg:grid-cols-2">
                  {preview.synonymCandidates.slice(0, 50).map((candidate) => (
                    <li
                      className="rounded-md border border-border bg-surface-subtle p-3"
                      key={`${candidate.lessonNumber}:${candidate.normalizedTitle}`}
                    >
                      <p className="font-medium text-foreground">
                        Занятие {candidate.lessonNumber} · {candidate.displayTitle}
                      </p>
                      <p className="text-caption text-muted-foreground">
                        {candidate.members
                          .map(
                            (member) => `${member.groupCode} ${member.problemNumber}${member.item}`,
                          )
                          .join(' · ')}
                      </p>
                      {candidate.hasGroupConflict ? (
                        <p className="mt-1 text-caption text-status-warning">
                          В одной группе совпали несколько названий — перед объединением выберите
                          одну задачу.
                        </p>
                      ) : null}
                    </li>
                  ))}
                </ul>
                {preview.synonymCandidates.length > 50 ? (
                  <p className="text-caption text-muted-foreground">
                    Показаны первые 50 кандидатов.
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ) : null}
          {preview.summary.invalid > 0 ? (
            <Alert tone="warning">
              <AlertContent>
                <AlertTitle>Строки с ошибками будут пропущены</AlertTitle>
                <AlertDescription>
                  Исправьте файл, если эти {preview.summary.invalid} строк тоже должны попасть в
                  базу. Остальные строки можно применить сейчас.
                </AlertDescription>
              </AlertContent>
            </Alert>
          ) : null}
          <div className="flex flex-wrap items-end justify-between gap-3">
            <Label className="grid gap-1 text-small">
              Показать
              <select
                className="h-9 rounded-md border border-input bg-surface px-3 text-small"
                onChange={(event) => setFilter(event.target.value as typeof filter)}
                value={filter}
              >
                <option value="changes">Изменения и ошибки</option>
                <option value="invalid">Только ошибки</option>
                <option value="create">Только новые</option>
                <option value="update">Только изменённые</option>
                <option value="unchanged">Без изменений</option>
              </select>
            </Label>
            <p className="text-caption text-muted-foreground">
              Показано {visibleRows.length} из {filteredRows.length}
            </p>
          </div>
          <div className="max-h-[38rem] overflow-auto rounded-md border border-border">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-surface-raised">
                <TableRow>
                  <TableHead>Строка</TableHead>
                  <TableHead>Задача</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>Действие</TableHead>
                  <TableHead>Диагностика</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleRows.map((row) => (
                  <TableRow key={`${row.sheet}:${row.row}`}>
                    <TableCell className="whitespace-nowrap font-num text-caption">
                      {row.sheet} · {row.row}
                    </TableCell>
                    <TableCell className="whitespace-nowrap font-num">{identity(row)}</TableCell>
                    <TableCell>{row.title ?? '—'}</TableCell>
                    <TableCell>{actionBadge(row.action)}</TableCell>
                    <TableCell className="min-w-64 text-caption text-muted-foreground">
                      {row.diagnostics.length
                        ? row.diagnostics.map((item) => item.message).join(' ')
                        : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {receipt?.state === 'applied' ? (
            <Alert tone="success">
              <AlertContent>
                <AlertTitle>Изменения применены</AlertTitle>
                <AlertDescription>
                  Создано {receipt.summary.created}, обновлено {receipt.summary.updated}, пропущено
                  с ошибками {receipt.summary.skippedInvalid}. Квитанция: {receipt.importId}.
                </AlertDescription>
                {confirmation === 'rollback' ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      disabled={pending}
                      onClick={() => onRollback(receipt)}
                      type="button"
                      variant="destructive"
                    >
                      Подтвердить откат
                    </Button>
                    <Button onClick={() => setConfirmation(null)} type="button" variant="outline">
                      Отмена
                    </Button>
                  </div>
                ) : (
                  <Button
                    className="mt-3"
                    disabled={pending}
                    onClick={() => setConfirmation('rollback')}
                    type="button"
                    variant="outline"
                  >
                    Откатить импорт
                  </Button>
                )}
              </AlertContent>
            </Alert>
          ) : receipt?.state === 'rolled_back' ? (
            <Alert>
              <AlertContent>
                <AlertTitle>Импорт отменён</AlertTitle>
                <AlertDescription>
                  Созданные задачи удалены, прежние значения восстановлены одной транзакцией.
                </AlertDescription>
              </AlertContent>
            </Alert>
          ) : confirmation === 'apply' ? (
            <Alert tone="warning">
              <AlertContent>
                <AlertTitle>Подтвердите запись в SQLite</AlertTitle>
                <AlertDescription>
                  Будет создано {preview.summary.create} и обновлено {preview.summary.update} задач.
                  Откат возможен, пока эти строки не изменены и новые задачи не используются.
                </AlertDescription>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    disabled={!selectionMatchesPreview || pending}
                    onClick={() => {
                      if (courseId && workbook) onApply(courseId, workbook, preview)
                    }}
                    type="button"
                  >
                    Подтвердить применение
                  </Button>
                  <Button onClick={() => setConfirmation(null)} type="button" variant="outline">
                    Отмена
                  </Button>
                </div>
              </AlertContent>
            </Alert>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                disabled={!selectionMatchesPreview || changedRows === 0 || pending}
                onClick={() => setConfirmation('apply')}
                type="button"
              >
                Применить изменения · {changedRows}
              </Button>
              {!selectionMatchesPreview ? (
                <p className="text-small text-muted-foreground">
                  После выбора другого курса или файла запустите проверку заново.
                </p>
              ) : null}
            </div>
          )}
        </section>
      ) : null}
    </div>
  )
}

export function ProblemImportPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Problem import requires Staff auth')
  const isAdmin = principal.role === 'admin'
  const client = useMemo(
    () =>
      createAdminCourseClient(authentication.client.runtime, {
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
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const catalog = useAdminCourseCatalogQuery(client, scope, undefined, isAdmin)
  const preview = useMutation({
    mutationFn: ({ courseId, workbook }: { courseId: string; workbook: File }) =>
      client.previewProblemImport(courseId, workbook),
    onError: (error) => authentication.handleApiError(error),
  })
  const apply = useMutation({
    mutationFn: ({
      courseId,
      workbook,
      review,
    }: {
      courseId: string
      workbook: File
      review: ProblemImportPreviewResponse
    }) => client.applyProblemImport(courseId, workbook, review.source.sha256, review.previewSha256),
    onError: (error) => authentication.handleApiError(error),
  })
  const rollback = useMutation({
    mutationFn: (receipt: ProblemImportReceipt) =>
      client.rollbackProblemImport(receipt.importId, receipt.version),
    onError: (error) => authentication.handleApiError(error),
  })
  const operationError = rollback.error ?? apply.error ?? preview.error
  const receipt = rollback.data ?? apply.data
  const reviewedWorkbook = preview.variables?.workbook

  if (!isAdmin) {
    return (
      <PageLayout title="Настройки задач" width="wide">
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }
  if (catalog.isPending) {
    return (
      <PageLayout title="Настройки задач" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (catalog.error || !catalog.data) {
    return (
      <PageLayout title="Настройки задач" width="wide">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void catalog.refetch()}
          state="error"
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description="Проверка XLSX из текущего процесса перед управляемым отказом от Google-листов."
      eyebrow="Admin"
      title="Настройки задач"
      width="wide"
    >
      <ProblemImportView
        courses={catalog.data.courses}
        {...(operationError ? { error: operationError } : {})}
        onApply={(courseId, workbook, review) => apply.mutate({ courseId, workbook, review })}
        onPreview={(courseId, workbook) => {
          apply.reset()
          rollback.reset()
          preview.mutate({ courseId, workbook })
        }}
        onRollback={(current) => rollback.mutate(current)}
        pending={preview.isPending || apply.isPending || rollback.isPending}
        {...(preview.data ? { preview: preview.data } : {})}
        {...(receipt ? { receipt } : {})}
        {...(reviewedWorkbook ? { reviewedWorkbook } : {})}
      />
    </PageLayout>
  )
}
