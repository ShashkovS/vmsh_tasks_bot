import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthentication, useAuthenticatedPrincipal, PageLayout } from '@vmsh/app-shell'
import {
  whiteboardCatalogSchema,
  whiteboardExportSchema,
  ApiResponseError,
  apiErrorSchema,
} from '@vmsh/contracts'
import { Button } from '@vmsh/ui'
import { Route } from './routes/whiteboard-export'

export function WhiteboardExportPage() {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const [includeStats, setIncludeStats] = useState(true)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')
  const [statsError, setStatsError] = useState(false)
  const abort = useRef<AbortController | null>(null)
  useEffect(() => () => abort.current?.abort(), [])
  async function get(path: string, signal?: AbortSignal) {
    const request = () =>
      fetch(`${auth.client.runtime.apiBase}/whiteboard-export${path}`, {
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        ...(signal ? { signal } : {}),
      })
    let response = await request()
    if (response.status === 401) {
      await auth.refresh()
      response = await request()
    }
    const payload: unknown = await response.json()
    if (!response.ok) {
      const e = new ApiResponseError(response.status, apiErrorSchema.parse(payload))
      auth.handleApiError(e)
      throw e
    }
    return payload
  }
  const catalog = useQuery({
    queryKey: ['whiteboard-export', principal.accountId],
    queryFn: async ({ signal }) => whiteboardCatalogSchema.parse(await get('', signal)),
    refetchOnWindowFocus: 'always',
  })
  const sheets = catalog.data?.sheets ?? []
  const courses = [...new Map(sheets.map((s) => [s.courseId, s])).values()]
  const course = courses.find((s) => s.courseId === search.course) ?? courses[0]
  const lessons = [
    ...new Map(
      sheets.filter((s) => s.courseId === course?.courseId).map((s) => [s.lessonNumber, s]),
    ).values(),
  ]
  const lesson = lessons.find((s) => s.lessonNumber === search.lesson) ?? lessons[0]
  const groups = sheets.filter(
    (s) => s.courseId === course?.courseId && s.lessonNumber === lesson?.lessonNumber,
  )
  const selected = groups.find((s) => s.groupId === search.group) ?? groups[0]
  async function generate(withStats = includeStats) {
    if (!selected || abort.current) return
    const controller = new AbortController()
    abort.current = controller
    setError('')
    setStatsError(false)
    setProgress('Загружаем условия…')
    try {
      const data = whiteboardExportSchema.parse(
        await get(`/${selected.groupLessonId}?statistics=${withStats ? 1 : 0}`, controller.signal),
      )
      if (data.statisticsError) {
        setStatsError(true)
        return
      }
      const { generateWhiteboard } = await import('./whiteboard-export-generator')
      const result = await generateWhiteboard(data, controller.signal, setProgress)
      controller.signal.throwIfAborted()
      const url = URL.createObjectURL(result.blob)
      const a = document.createElement('a')
      a.href = url
      a.download = result.filename
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 30_000)
    } catch (e) {
      if (!controller.signal.aborted)
        setError(e instanceof Error ? e.message : 'Не удалось подготовить архив')
    } finally {
      abort.current = null
      setProgress('')
    }
  }
  return (
    <PageLayout title="Материалы для разбора" description="Условия задач в PNG для Zoom Whiteboard">
      <div className="space-y-5 rounded-xl border bg-card p-5">
        {catalog.isPending ? (
          <p>Загружаем занятия…</p>
        ) : catalog.isError ? (
          <div role="alert">
            Не удалось загрузить занятия.{' '}
            <Button onClick={() => void catalog.refetch()}>Повторить</Button>
          </div>
        ) : sheets.length === 0 ? (
          <p>Нет доступных опубликованных листков.</p>
        ) : (
          <>
            <fieldset disabled={Boolean(progress)} className="grid gap-4 sm:grid-cols-3">
              <label className="space-y-2">
                Курс
                <select
                  className="block w-full rounded-md border bg-background p-2"
                  value={course?.courseId}
                  onChange={(e) => {
                    setStatsError(false)
                    void navigate({ search: { course: e.target.value } })
                  }}
                >
                  {courses.map((s) => (
                    <option key={s.courseId} value={s.courseId}>
                      {s.courseName}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2">
                Занятие
                <select
                  className="block w-full rounded-md border bg-background p-2"
                  value={lesson?.lessonNumber}
                  onChange={(e) => {
                    setStatsError(false)
                    void navigate({
                      search: { course: course?.courseId, lesson: Number(e.target.value) },
                    })
                  }}
                >
                  {lessons.map((s) => (
                    <option key={s.lessonNumber} value={s.lessonNumber}>
                      Занятие {s.lessonNumber}
                      {s.lessonTitle ? ` · ${s.lessonTitle}` : ''}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2">
                Уровень
                <select
                  className="block w-full rounded-md border bg-background p-2"
                  value={selected?.groupId}
                  onChange={(e) => {
                    setStatsError(false)
                    void navigate({
                      search: {
                        course: course?.courseId,
                        lesson: lesson?.lessonNumber,
                        group: e.target.value,
                      },
                    })
                  }}
                >
                  {groups.map((s) => (
                    <option key={s.groupId} value={s.groupId}>
                      {s.groupCode} · {s.groupName}
                    </option>
                  ))}
                </select>
              </label>
            </fieldset>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeStats}
                disabled={Boolean(progress)}
                onChange={(e) => setIncludeStats(e.target.checked)}
              />
              Добавить статистику
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <Button disabled={Boolean(progress)} onClick={() => void generate()}>
                Скачать ZIP
              </Button>
              {progress && (
                <>
                  <span role="status">{progress}</span>
                  <Button variant="outline" onClick={() => abort.current?.abort()}>
                    Отмена
                  </Button>
                </>
              )}
            </div>
            {statsError && (
              <div role="alert" className="space-y-3">
                <p>
                  Не удалось загрузить статистику. Можно повторить запрос или скачать только
                  условия.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => void generate(true)}>Повторить</Button>
                  <Button variant="outline" onClick={() => void generate(false)}>
                    Скачать без статистики
                  </Button>
                </div>
              </div>
            )}
            {error && <p role="alert">{error}. Попробуйте ещё раз.</p>}
            <p className="text-sm text-muted-foreground">
              Распакуйте архив и перетащите PNG на доску Zoom Whiteboard.
            </p>
          </>
        )}
      </div>
    </PageLayout>
  )
}
