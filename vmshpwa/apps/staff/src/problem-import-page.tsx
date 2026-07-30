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
  onPreview,
}: {
  courses: AdminCourse[]
  error?: Error
  pending: boolean
  preview?: ProblemImportPreviewResponse
  onPreview: (courseId: string, workbook: File) => void
}) {
  const [courseId, setCourseId] = useState(
    courses.find((course) => course.status === 'active')?.courseId ?? courses[0]?.courseId ?? '',
  )
  const [workbook, setWorkbook] = useState<File>()
  const [filter, setFilter] = useState<'changes' | ProblemImportAction>('changes')
  const filteredRows = useMemo(() => {
    if (!preview) return []
    if (filter === 'changes') return preview.rows.filter((row) => row.action !== 'unchanged')
    return preview.rows.filter((row) => row.action === filter)
  }, [filter, preview])
  const visibleRows = filteredRows.slice(0, 300)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (courseId && workbook) onPreview(courseId, workbook)
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
                onChange={(event) => setCourseId(event.target.value)}
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
                onChange={(event) => setWorkbook(event.target.files?.[0])}
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
            <AlertTitle>Файл не проверен</AlertTitle>
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
          <p className="text-small text-muted-foreground">
            Применение и откат появятся после отдельной серверной реализации с журналом изменений.
          </p>
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
        {...(preview.error ? { error: preview.error } : {})}
        onPreview={(courseId, workbook) => preview.mutate({ courseId, workbook })}
        pending={preview.isPending}
        {...(preview.data ? { preview: preview.data } : {})}
      />
    </PageLayout>
  )
}
