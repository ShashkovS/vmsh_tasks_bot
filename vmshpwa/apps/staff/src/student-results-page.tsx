import { useDeferredValue, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { onlineManager, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createStudentResultsClient,
  StaffCapabilityBoundary,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import type { StudentResultsOverview } from '@vmsh/contracts'
import {
  Button,
  Input,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@vmsh/ui'
import { studentNameMatchesSearch } from './student-directory-search'
import { ResultCondition, ResultHistory, ResultMark } from './student-results-history'

type Search = {
  student?: string | undefined
  course?: string | undefined
  lesson?: number | undefined
}
type Props = { search: Search; onChange: (search: Search, replace?: boolean) => void }
type Group = StudentResultsOverview['summaries'][number]['groups'][number]
const selectStyle =
  'h-10 min-w-0 max-w-full rounded-md border border-input bg-surface px-2 text-small focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring'
function Tables({
  groups,
  onGrade,
}: {
  groups: Group[]
  onGrade: (id: string, label: string) => void
}) {
  return (
    <div className="space-y-2">
      {groups.map((g) => (
        <div key={g.groupId} className="min-w-0">
          <p className="mb-1 text-caption text-muted-foreground">{g.name}</p>
          <div
            className="overflow-x-auto rounded border"
            // Scrollable tables need keyboard focus (student-results.md, mobile acceptance).
            // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
            tabIndex={0}
            role="region"
            aria-label={`Плюсы · ${g.name}`}
          >
            <table className="w-full border-collapse text-center text-small">
              <thead>
                <tr>
                  {g.problems.map((p) => (
                    <th
                      key={p.problemId}
                      scope="col"
                      className="min-w-11 border-r bg-surface-subtle px-1 py-1 font-medium last:border-r-0"
                    >
                      {p.label}
                      <span className="mx-auto block w-24 whitespace-normal break-words text-xs font-normal leading-tight text-muted-foreground">
                        {p.title}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  {g.problems.map((p) => (
                    <td key={p.problemId} className="border-r border-t last:border-r-0">
                      <button
                        type="button"
                        className="min-h-10 w-full px-2 hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                        aria-label={`История оценки · задача ${p.label} · ${g.name}`}
                        onClick={(event) => {
                          event.currentTarget.focus()
                          onGrade(p.problemId, `${p.label} · ${g.name}`)
                        }}
                      >
                        <ResultMark
                          value={p.current?.verdict ?? null}
                          symbol={p.current?.symbol ?? ''}
                        />
                      </button>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}

export function StudentResultsPage(props: Props) {
  return (
    <StaffCapabilityBoundary capability="audit.read">
      <StudentResultsWorkspace {...props} />
    </StaffCapabilityBoundary>
  )
}
// design-system/05-pages-and-flows.md; full archive decisions: docs/student-results.md.
function StudentResultsWorkspace({ search, onChange }: Props) {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () => createStudentResultsClient(auth.client.runtime, auth.refresh),
    [auth.client.runtime, auth.refresh],
  )
  const online = useSyncExternalStore(
    (notify) => onlineManager.subscribe(notify),
    () => onlineManager.isOnline(),
    () => true,
  )
  const cache = useQueryClient()
  const [query, setQuery] = useState('')
  const deferred = useDeferredValue(query)
  const [searchOpen, setSearchOpen] = useState(!search.student)
  const [grade, setGrade] = useState<{ id: string; label: string } | null>(null)
  const detailRef = useRef<HTMLElement>(null)
  const scrollRequested = useRef(false)
  const scope = principal.accountId
  const directory = useQuery({
    queryKey: ['student-results', scope, 'directory'],
    queryFn: client.directory,
    staleTime: 60_000,
  })
  const overview = useQuery({
    queryKey: ['student-results', scope, 'overview', search.student, search.course],
    queryFn: () => client.overview(search.student!, search.course),
    enabled: Boolean(search.student),
  })
  const data = overview.data
  const course = search.course ?? data?.courseId ?? undefined
  const number =
    search.lesson ?? data?.lessons.find((l) => l.hasActivity)?.number ?? data?.lessons[0]?.number
  const lesson = useQuery({
    queryKey: ['student-results', scope, 'lesson', search.student, course, number],
    queryFn: () => client.lesson(search.student!, course!, number!),
    enabled: Boolean(search.student && course && number !== undefined),
  })
  const matches = useMemo(
    () =>
      (directory.data?.students ?? [])
        .filter((s) => !deferred.trim() || studentNameMatchesSearch(s.name, deferred))
        .slice(0, 50),
    [directory.data, deferred],
  )
  useEffect(() => {
    if (data && (search.course !== course || search.lesson !== number))
      onChange({ student: search.student, course, lesson: number }, true)
  }, [data, course, number, search.course, search.lesson, search.student, onChange])
  useEffect(() => {
    if (scrollRequested.current && lesson.data) {
      detailRef.current?.scrollIntoView({ block: 'start' })
      detailRef.current?.focus({ preventScroll: true })
      scrollRequested.current = false
    }
  }, [lesson.data])
  const refresh = () => void cache.invalidateQueries({ queryKey: ['student-results', scope] })
  const chooseLesson = (value: number) => {
    if (value === number) {
      detailRef.current?.scrollIntoView({ block: 'start' })
      detailRef.current?.focus({ preventScroll: true })
    } else {
      scrollRequested.current = true
      onChange({ student: search.student, course, lesson: value })
    }
  }
  return (
    <main className="mx-auto w-full min-w-0 max-w-6xl space-y-4 p-2 sm:p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="mr-auto text-lg font-semibold">Результаты школьника</h1>
        <Button variant="outline" size="sm" onClick={refresh}>
          Обновить
        </Button>
      </header>
      {!online && (
        <p role="status" className="text-small text-muted-foreground">
          Нет соединения. Доступны загруженные результаты; обновление продолжится после подключения.
        </p>
      )}
      {(!search.student || searchOpen || overview.isError) && (
        <section aria-label="Поиск школьника" className="space-y-2">
          <label className="text-small font-medium" htmlFor="results-student-search">
            Фамилия и имя
          </label>
          <Input
            id="results-student-search"
            autoComplete="off"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти школьника…"
          />
          {directory.isPending && <p role="status">Загружаем список…</p>}
          {directory.isError && (
            <p role="alert">
              Не удалось загрузить список. Проверьте соединение и нажмите «Обновить».
            </p>
          )}
          <ul className="max-h-72 overflow-auto divide-y rounded border">
            {matches.map((s) => (
              <li key={s.studentId}>
                <button
                  className="w-full px-3 py-2 text-left hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                  onClick={() => {
                    setSearchOpen(false)
                    setGrade(null)
                    onChange({ student: s.studentId })
                  }}
                >
                  <span className="block text-small font-semibold">{s.name}</span>
                  <span className="text-caption text-muted-foreground">
                    {[s.grade ? `${s.grade} кл.` : '', s.middleName, s.groups]
                      .filter(Boolean)
                      .join(' · ') || 'Архивный школьник'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {directory.data && !matches.length && <p>Школьники не найдены.</p>}
          {matches.length === 50 && (
            <p className="text-caption text-muted-foreground">
              Первые 50 совпадений — уточните имя.
            </p>
          )}
        </section>
      )}
      {overview.isError && (
        <p role="alert">
          Не удалось открыть результаты. Проверьте соединение или выберите другого школьника.
        </p>
      )}
      {search.student && overview.isPending && <p role="status">Загружаем сводку…</p>}
      {data && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <div className="mr-auto min-w-0">
              <h2 className="font-semibold">{data.student.name}</h2>
              <p className="text-caption text-muted-foreground">
                {[data.student.grade ? `${data.student.grade} кл.` : '', data.student.middleName]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setSearchOpen((v) => !v)}>
              Сменить школьника
            </Button>
            {data.courses.length > 1 && (
              <select
                className={selectStyle}
                aria-label="Курс"
                value={course}
                onChange={(e) => {
                  setGrade(null)
                  onChange({ student: search.student, course: e.target.value })
                }}
              >
                {data.courses.map((c) => (
                  <option key={c.courseId} value={c.courseId}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
          </div>
          <section
            aria-label="Плюсы по всем занятиям"
            className="grid min-w-0 gap-3 lg:grid-cols-2"
          >
            {data.summaries.map((s) => (
              <article
                key={s.number}
                className={`min-w-0 space-y-2 rounded-lg border p-2 ${s.number === number ? 'border-primary bg-accent/30' : ''}`}
              >
                <Button variant="ghost" size="sm" onClick={() => chooseLesson(s.number)}>
                  Занятие {s.number}
                  {s.number === number ? ' · выбрано' : ''}
                </Button>
                <Tables groups={s.groups} onGrade={(id, label) => setGrade({ id, label })} />
              </article>
            ))}
          </section>
          {!data.summaries.length && (
            <p className="text-small text-muted-foreground">Результатов и посылок пока нет.</p>
          )}
          {course && number !== undefined && (
            <section
              ref={detailRef}
              tabIndex={-1}
              aria-label="История занятия"
              className="min-w-0 space-y-4 scroll-mt-3"
            >
              <div className="flex flex-wrap items-center gap-2 border-b pb-2">
                <h2 className="mr-auto font-semibold">История занятия</h2>
                <select
                  aria-label="Занятие"
                  className={selectStyle}
                  value={number}
                  onChange={(e) => chooseLesson(Number(e.target.value))}
                >
                  {data.lessons.map((l) => (
                    <option key={l.number} value={l.number}>
                      Занятие {l.number}
                      {l.hasActivity ? '' : ' · без результатов'}
                    </option>
                  ))}
                </select>
              </div>
              {lesson.isPending && <p role="status">Загружаем посылки…</p>}
              {lesson.isError && (
                <p role="alert">
                  История недоступна.{' '}
                  <Button variant="outline" onClick={() => void lesson.refetch()}>
                    Повторить
                  </Button>
                </p>
              )}
              {lesson.data && (
                <>
                  {lesson.data.notes.some((n) => n.reaction || n.action !== 'current') && (
                    <aside className="rounded border bg-surface-subtle p-3">
                      <h3 className="mb-2 text-small font-semibold">Пометки Zoom-приёма</h3>
                      {lesson.data.notes
                        .filter((n) => n.reaction || n.action !== 'current')
                        .map((n, i) => (
                          <p key={`${n.id}-${i}`} className="text-small">
                            {n.action === 'undo'
                              ? 'Отмена: '
                              : n.action === 'changed'
                                ? 'Пометки: '
                                : ''}
                            {n.reaction ?? 'сняты'}{' '}
                            <span className="text-caption text-muted-foreground">
                              · {n.author} ·{' '}
                              {new Date(n.reaction_at ?? n.ts).toLocaleString('ru-RU')}
                            </span>
                          </p>
                        ))}
                    </aside>
                  )}
                  {!lesson.data.groups.length && (
                    <p className="text-small text-muted-foreground">
                      Отправленных решений и тестовых попыток в этом занятии нет.
                    </p>
                  )}
                  {lesson.data.groups.map((g) => (
                    <section key={g.groupId} className="min-w-0 space-y-4">
                      <h3 className="border-b pb-1 font-semibold">{g.name}</h3>
                      {g.problems.map((p) => (
                        <article
                          key={`${search.student}-${p.problemId}`}
                          className="min-w-0 space-y-3 rounded-lg border p-3 sm:p-4"
                        >
                          <header className="flex flex-wrap items-center gap-2">
                            <h4 className="mr-auto min-w-0 break-words font-semibold">
                              Задача {p.label}
                              {p.title ? ` · ${p.title}` : ''}
                            </h4>
                            <span className="text-caption text-muted-foreground">
                              Текущий результат
                            </span>
                            <ResultMark
                              value={p.current?.verdict ?? null}
                              symbol={p.current?.symbol ?? ''}
                            />
                            {p.reviewUrl && (
                              <a className="text-small text-primary underline" href={p.reviewUrl}>
                                Открыть проверку
                              </a>
                            )}
                          </header>
                          <ResultCondition document={p.document} legacyText={p.legacyCondition} />
                          <ResultHistory
                            client={client}
                            scope={scope}
                            student={search.student!}
                            problem={p.problemId}
                            initial={p.history}
                          />
                        </article>
                      ))}
                    </section>
                  ))}
                </>
              )}
            </section>
          )}
        </>
      )}
      <Dialog
        open={grade !== null}
        onOpenChange={(open) => {
          if (!open) setGrade(null)
        }}
      >
        <DialogContent className="max-h-[85svh] overflow-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>История оценки · {grade?.label}</DialogTitle>
            <DialogDescription>Все сохранённые изменения и ответы по задаче</DialogDescription>
          </DialogHeader>
          {grade && search.student && (
            <ResultHistory
              key={`${search.student}-${grade.id}`}
              client={client}
              scope={scope}
              student={search.student}
              problem={grade.id}
            />
          )}
        </DialogContent>
      </Dialog>
    </main>
  )
}
