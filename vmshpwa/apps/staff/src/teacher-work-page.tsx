import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  PageLayout,
  PageStatePanel,
  createTeacherWorkClient,
  useAuthentication,
  useAuthenticatedPrincipal,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  principalQueryKey,
  teacherWorkPreviewSchema,
  teacherWorkStoredRowsSchema,
  teacherWorkRosterBaseSchema,
  type TeacherWorkCatalog,
  type TeacherWorkCommand,
  type TeacherWorkDetails,
  type TeacherWorkInputs,
  type TeacherWorkPreview,
  type TeacherWorkReport,
} from '@vmsh/contracts'
import {
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
  Tabs,
  TabsList,
  TabsTrigger,
  Textarea,
} from '@vmsh/ui'
import { UsersSectionTabs, type UsersSection } from './users-section-tabs'
import { acceptAliasReceipt } from './teacher-work-inputs'
import './teacher-work.css'

// design-system/05-pages-and-flows.md, Staff; authoritative rules: docs/teacher-work.md.
export type WorkSection = 'report' | 'school' | 'zoom' | 'settings'
export type WorkSearch = {
  section?: WorkSection | undefined
  course?: string | undefined
  first?: number | undefined
  last?: number | undefined
  q?: string | undefined
}
type Save = (
  command:
    | Omit<Extract<TeacherWorkCommand, { action: 'alias' }>, 'courseId' | 'idempotencyKey'>
    | Omit<Extract<TeacherWorkCommand, { action: 'settings' }>, 'courseId' | 'idempotencyKey'>
    | Omit<Extract<TeacherWorkCommand, { action: 'roster' }>, 'courseId' | 'idempotencyKey'>
    | Omit<Extract<TeacherWorkCommand, { action: 'override' }>, 'courseId' | 'idempotencyKey'>,
  onSuccess?: (receipt: { version: number }) => void,
) => void

function sourceName(source: string): string {
  switch (source) {
    case 'log':
      return t`По логу`
    case 'series':
      return t`По серии`
    case 'estimate':
      return t`Оценка`
    case 'roster':
      return t`По распределению`
    case 'manual':
      return t`Вручную`
    default:
      return t`Время неизвестно`
  }
}
function h(value: number | null, places = 1) {
  return value === null ? '—' : value.toFixed(places)
}
const selectClass = 'h-9 max-w-full rounded-md border border-input bg-background px-2 text-small'

function TeacherSelect({
  value,
  teachers,
  onChange,
  label,
  disabled = false,
}: {
  value: string | null
  teachers: TeacherWorkCatalog['teachers']
  onChange: (id: string | null) => void
  label: string
  disabled?: boolean
}) {
  return (
    <select
      aria-label={label}
      className={selectClass}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value || null)}
      value={value ?? ''}
    >
      <option value="">{t`Выберите преподавателя`}</option>
      {teachers.map((teacher) => (
        <option key={teacher.teacherId} value={teacher.teacherId}>
          {teacher.surname} {teacher.name} · {teacher.id}
        </option>
      ))}
    </select>
  )
}

export function TeacherWorkReportView({
  report,
  onCell,
}: {
  report: TeacherWorkReport
  onCell: (key: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const [fallback, setFallback] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(report.tsv)
      setCopied(true)
    } catch {
      setFallback(true)
    }
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={!report.run} onClick={() => void copy()} variant="outline">
          <Trans>Копировать TSV</Trans>
        </Button>
        <span className="text-caption text-muted-foreground" role="status">
          {copied ? t`Отчёт скопирован` : t`Дни очно и Zoom · занятия письменно · часы`}
        </span>
      </div>
      {fallback ? (
        <Label className="grid gap-1">
          <Trans>Выделите и скопируйте отчёт</Trans>
          <Textarea onFocus={(e) => e.target.select()} readOnly rows={6} value={report.tsv} />
        </Label>
      ) : null}
      {!report.run ? (
        <PageStatePanel
          state="empty"
          title={t`Учёт ещё не рассчитан`}
          description={t`Запустите пересчёт, чтобы собрать работу преподавателей.`}
        />
      ) : report.rows.length === 0 ? (
        <PageStatePanel
          state="empty"
          title={t`За выбранные занятия работы нет`}
          description={t`Проверьте диапазон или добавьте подтверждённые очные смены и Zoom-подписи.`}
        />
      ) : (
        <div
          aria-label={t`Таблица учёта работы`}
          className="teacher-work-scroll"
          role="region"
          // Keyboard scrolling of this named region is intentional.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
        >
          <table className="teacher-work-table">
            <caption className="sr-only">
              <Trans>
                Работа преподавателей по занятиям и видам. Выберите часы для подробностей и
                поправки.
              </Trans>
            </caption>
            <thead>
              <tr>
                <th className="tw-id" rowSpan={3}>
                  id
                </th>
                <th className="tw-surname" rowSpan={3}>
                  <Trans>Фамилия</Trans>
                </th>
                <th className="tw-name" rowSpan={3}>
                  <Trans>Имя</Trans>
                </th>
                <th rowSpan={3}>
                  <Trans>Отчество</Trans>
                </th>
                {[
                  t`РазОчн`,
                  t`РазZoom`,
                  t`РазПисм`,
                  t`РазСум`,
                  t`ЧасОчн`,
                  t`ЧасZoom`,
                  t`ЧасПисьм`,
                  t`ЧасСум`,
                ].map((label) => (
                  <th key={label} rowSpan={3}>
                    {label}
                  </th>
                ))}
                {report.columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
              <tr>
                {report.columns.map((column) => (
                  <th key={column.key}>{column.lesson}</th>
                ))}
              </tr>
              <tr>
                {report.columns.map((column) => (
                  <th key={column.key}>{column.date.slice(5)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.teacherId}>
                  <th className="tw-id" scope="row">
                    {row.id}
                  </th>
                  <td className="tw-surname">{row.surname}</td>
                  <td className="tw-name">{row.name}</td>
                  <td>{row.middlename}</td>
                  <td>{row.counts.school}</td>
                  <td>{row.counts.zoom}</td>
                  <td>{row.counts.written}</td>
                  <td>{row.counts.school + row.counts.zoom + row.counts.written}</td>
                  <td>{h(row.totals.school)}</td>
                  <td>{h(row.totals.zoom)}</td>
                  <td>{h(row.totals.written)}</td>
                  <td>{h(row.totalHours, 2)}</td>
                  {row.cells.map((cell, index) => {
                    const column = report.columns[index]!
                    const key =
                      cell.keys[0] ??
                      `${column.kind}:${row.id}:${column.kind === 'written' ? column.lesson : column.date}`
                    return (
                      <td key={column.key}>
                        <button
                          aria-label={t`${row.surname} ${row.name}, занятие ${column.lesson}, ${column.label}, ${h(cell.hours)} ч`}
                          className={`tw-cell ${cell.sources.includes('manual') ? 'tw-manual' : ''} ${cell.stale ? 'tw-stale' : ''}`}
                          onClick={() => onCell(key)}
                          title={
                            cell.stale
                              ? t`Требует повторной проверки`
                              : cell.sources.map(sourceName).join(', ')
                          }
                          type="button"
                        >
                          {h(cell.hours)}
                          {cell.stale ? ' *' : cell.anomalies.length ? ' !' : ''}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-caption text-muted-foreground">
        <Trans>
          Суммы считаются до округления. «—» — неполные данные; «!» — оценка или разрыв лога; «*» —
          ручная поправка требует повторной проверки.
        </Trans>
      </p>
    </div>
  )
}

function AliasEditor({
  signature,
  teachers,
  saving,
  onSave,
}: {
  signature: TeacherWorkInputs['signatures'][number]
  teachers: TeacherWorkCatalog['teachers']
  saving: boolean
  onSave: Save
}) {
  const [teacher, setTeacher] = useState<string | null>(
    signature.alias?.teacher_id ? `u-${signature.alias.teacher_id}` : null,
  )
  return (
    <tr>
      <th className="max-w-72 break-words text-left" scope="row">
        {signature.name || t`Без подписи`}
      </th>
      <td>
        {signature.count}
        <br />
        <span className="text-caption">
          {signature.firstAt.slice(0, 10)} — {signature.lastAt.slice(0, 10)}
        </span>
      </td>
      <td>
        <TeacherSelect
          disabled={saving}
          label={t`Преподаватель для ${signature.name}`}
          onChange={setTeacher}
          teachers={teachers}
          value={teacher}
        />
        <div className="text-caption text-muted-foreground">
          {signature.candidates.map((c) => c.label).join(' · ')}
        </div>
        <details>
          <summary>
            <Trans>Примеры событий</Trans>
          </summary>
          {signature.examples.map((e) => (
            <p key={e.id}>
              {e.event_ts} · {e.event}
            </p>
          ))}
        </details>
      </td>
      <td>
        <span>
          {signature.alias?.state === 'ignored'
            ? t`Игнорируется`
            : signature.alias?.state === 'mapped'
              ? t`Сопоставлено`
              : t`Не сопоставлено`}
        </span>
        <div className="flex flex-wrap gap-1">
          <Button
            disabled={saving || !teacher}
            onClick={() =>
              onSave({
                action: 'alias',
                name: signature.name,
                state: 'mapped',
                teacherId: teacher,
                expectedVersion: signature.alias?.version ?? 0,
              })
            }
            size="sm"
            variant="outline"
          >
            <Trans>Сопоставить</Trans>
          </Button>
          {signature.alias && signature.alias.state !== 'unresolved' ? (
            <Button
              disabled={saving}
              onClick={() =>
                onSave({
                  action: 'alias',
                  name: signature.name,
                  state: 'unresolved',
                  teacherId: null,
                  expectedVersion: signature.alias!.version,
                })
              }
              size="sm"
              variant="ghost"
            >
              <Trans>Снять сопоставление</Trans>
            </Button>
          ) : null}
          <Button
            disabled={saving}
            onClick={() =>
              onSave({
                action: 'alias',
                name: signature.name,
                state: 'ignored',
                teacherId: null,
                expectedVersion: signature.alias?.version ?? 0,
              })
            }
            size="sm"
            variant="ghost"
          >
            <Trans>Игнорировать</Trans>
          </Button>
        </div>
      </td>
    </tr>
  )
}

function ZoomView({
  inputs,
  teachers,
  saving,
  onSave,
  report,
  onCell,
}: {
  inputs: TeacherWorkInputs
  teachers: TeacherWorkCatalog['teachers']
  saving: boolean
  onSave: Save
  report?: TeacherWorkReport | undefined
  onCell: (key: string) => void
}) {
  const [all, setAll] = useState(false),
    [query, setQuery] = useState(''),
    [unresolved, setUnresolved] = useState(true)
  const signatures = inputs.signatures.filter(
    (s) =>
      (all || s.teacherLike) &&
      (!unresolved || !s.alias || s.alias.state === 'unresolved') &&
      s.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  )
  return (
    <div className="space-y-3">
      <p className="text-small">
        <Trans>
          Сопоставления относятся только к выбранному курсу и сезону. Подсказка имени требует вашего
          подтверждения.
        </Trans>{' '}
        <Trans>
          Изменения сохраняются сразу. Отчёт обновится по кнопке пересчёта или по расписанию.
        </Trans>
      </p>
      <div className="flex flex-wrap gap-4">
        <Label className="grid gap-1">
          <Trans>Поиск подписи</Trans>
          <Input onChange={(e) => setQuery(e.target.value)} value={query} />
        </Label>
        <Label className="flex items-center gap-2">
          <Checkbox checked={all} onCheckedChange={(v) => setAll(v === true)} />
          <Trans>Все подписи</Trans>
        </Label>
        <Label className="flex items-center gap-2">
          <Checkbox checked={unresolved} onCheckedChange={(v) => setUnresolved(v === true)} />
          <Trans>Только несопоставленные</Trans>
        </Label>
      </div>
      <div className="overflow-x-auto">
        <table className="teacher-work-inputs">
          <caption className="sr-only">
            <Trans>Zoom-подписи</Trans>
          </caption>
          <thead>
            <tr>
              <th>
                <Trans>Подпись</Trans>
              </th>
              <th>
                <Trans>События</Trans>
              </th>
              <th>
                <Trans>Преподаватель</Trans>
              </th>
              <th>
                <Trans>Решение</Trans>
              </th>
            </tr>
          </thead>
          <tbody>
            {signatures.map((s) => (
              <AliasEditor
                key={`${s.name}:${s.alias?.version ?? 0}`}
                onSave={onSave}
                saving={saving}
                signature={s}
                teachers={teachers}
              />
            ))}
          </tbody>
        </table>
      </div>
      {signatures.length === 0 ? (
        <p role="status">
          <Trans>Подписей по этому фильтру нет.</Trans>
        </p>
      ) : null}
      <h2 className="text-subtitle">
        <Trans>Разрывы и оценки Zoom</Trans>
      </h2>
      <ul>
        {report?.rows.flatMap((row) =>
          row.cells
            .filter((c) => c.anomalies.length > 0)
            .map((cell) => (
              <li key={`${row.teacherId}:${cell.columnKey}`}>
                <Button onClick={() => onCell(cell.keys[0]!)} variant="link">
                  {row.surname} {row.name} · {cell.columnKey} · {h(cell.hours)} <Trans>ч</Trans>
                </Button>
              </li>
            )),
        )}
      </ul>
    </div>
  )
}

function readRosterPreview(key: string): TeacherWorkPreview | null {
  try {
    const value = localStorage.getItem(key + ':preview')
    return value ? teacherWorkPreviewSchema.parse(JSON.parse(value) as unknown) : null
  } catch {
    return null
  }
}

export function TeacherWorkRosterView({
  inputs,
  teachers,
  saving,
  onSave,
  onPreview,
  draftKey,
}: {
  inputs: TeacherWorkInputs
  teachers: TeacherWorkCatalog['teachers']
  saving: boolean
  onSave: Save
  onPreview: (text: string) => Promise<TeacherWorkPreview>
  draftKey: string
}) {
  const [raw, setRaw] = useState(() => {
    try {
      return localStorage.getItem(draftKey) ?? ''
    } catch {
      return ''
    }
  })
  const [preview, setPreview] = useState<TeacherWorkPreview | null>(() =>
    readRosterPreview(draftKey),
  )
  const [eventId, setEventId] = useState(() => {
    try {
      return localStorage.getItem(draftKey + ':event') ?? ''
    } catch {
      return ''
    }
  })
  const [base, setBase] = useState(() => {
    try {
      const stored = localStorage.getItem(draftKey + ':base')
      return stored ? teacherWorkRosterBaseSchema.parse(JSON.parse(stored) as unknown) : null
    } catch {
      return null
    }
  })
  const [error, setError] = useState<string | null>(null),
    [previewing, setPreviewing] = useState(false),
    [needsChoiceOnly, setNeedsChoiceOnly] = useState(false),
    [replace, setReplace] = useState(false)
  useEffect(() => {
    try {
      localStorage.setItem(draftKey + ':preview', JSON.stringify(preview))
      localStorage.setItem(draftKey + ':event', eventId)
      localStorage.setItem(draftKey + ':base', JSON.stringify(base))
    } catch {
      /* Raw text reports storage failure. */
    }
  }, [draftKey, preview, eventId, base])
  const event = inputs.events.find((e) => e.public_id === eventId)
  const existing = inputs.rosters.find((r) => r.eventPublicId === eventId)
  const unmatchedCount =
    preview?.rows.filter((r) => !r.teacherId && r.candidates.length === 0).length ?? 0
  const conflict = Boolean(
    base &&
    event &&
    (base.eventVersion !== event.version || base.expectedVersion !== (existing?.version ?? 0)),
  )
  function bindEvent(value: string) {
    setEventId(value)
    const selected = inputs.events.find((e) => e.public_id === value)
    setBase(
      selected
        ? {
            eventId: value,
            eventVersion: selected.version,
            expectedVersion: inputs.rosters.find((r) => r.eventPublicId === value)?.version ?? 0,
          }
        : null,
    )
  }
  function credited(row: TeacherWorkPreview['rows'][number]): number | null {
    if (!event) return null
    const previous = inputs.shifts.find(
      (s) => s.eventId === eventId && s.teacherId === row.teacherId,
    )
    const clock = (stamp: string) =>
      new Intl.DateTimeFormat('en-GB', {
        timeZone: inputs.timezone,
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
      }).format(new Date(stamp))
    const minutes = (value: string) => {
      const [h, m] = value.split(':').map(Number)
      return h! * 60 + m!
    }
    const actual =
      (Date.parse(event.ends_at) - Date.parse(event.starts_at)) / 3600000 +
      (row.endsTime ? (minutes(row.endsTime) - minutes(clock(event.ends_at))) / 60 : 0) -
      (row.startsTime ? (minutes(row.startsTime) - minutes(clock(event.starts_at))) / 60 : 0)
    const standard =
      (Date.parse(previous?.standardEndsAt ?? event.ends_at) -
        Date.parse(previous?.standardStartsAt ?? event.starts_at)) /
      3600000
    if (actual <= 0) return null
    return Math.max(0, (previous?.normHours ?? inputs.settings.norm_hours) + actual - standard)
  }
  function changeRaw(text: string) {
    setRaw(text)
    setPreview(null)
    try {
      localStorage.setItem(draftKey, text)
    } catch {
      setError(t`Черновик не сохраняется в этом браузере. Не закрывайте вкладку до отправки.`)
    }
  }
  async function parse() {
    setPreviewing(true)
    setError(null)
    try {
      const p = await onPreview(raw)
      setPreview(p)
      setNeedsChoiceOnly(false)
      if (p.eventCandidates.length === 1) bindEvent(p.eventCandidates[0]!)
      else if (eventId) bindEvent(eventId)
    } catch {
      setError(t`Не удалось разобрать распределение. Повторите запрос.`)
    } finally {
      setPreviewing(false)
    }
  }
  function update(rowId: string, patch: Partial<TeacherWorkPreview['rows'][number]>) {
    if (preview)
      setPreview({
        ...preview,
        rows: preview.rows.map((r) => (r.rowId === rowId ? { ...r, ...patch } : r)),
      })
  }
  function save(state: 'draft' | 'confirmed') {
    if (!preview || !event || !base || conflict) return
    onSave(
      {
        action: 'roster',
        rawText: raw,
        rows: teacherWorkStoredRowsSchema.parse(preview.rows),
        eventId,
        eventVersion: base.eventVersion,
        expectedVersion: base.expectedVersion,
        state,
        replace,
      },
      (receipt) => setBase({ ...base, expectedVersion: receipt.version }),
    )
  }
  return (
    <div className="space-y-3">
      <Label className="grid gap-1">
        <Trans>Распределение из оргчата</Trans>
        <Textarea onChange={(e) => changeRaw(e.target.value)} rows={8} value={raw} />
      </Label>
      <Button
        disabled={!raw.trim() || previewing || saving}
        onClick={() => void parse()}
        variant="outline"
      >
        {previewing ? t`Разбираем…` : t`Предварительный просмотр`}
      </Button>
      {conflict ? (
        <p className="text-status-warning" role="alert">
          <Trans>
            Событие или распределение изменилось. Сверьте сохранённые данные и повторите
            предварительный просмотр.
          </Trans>
        </p>
      ) : null}
      {error ? (
        <p className="text-status-error" role="alert">
          {error}
        </p>
      ) : null}
      <Label className="grid gap-1">
        <Trans>Очное событие</Trans>
        <select className={selectClass} onChange={(e) => bindEvent(e.target.value)} value={eventId}>
          <option value="">{t`Выберите событие`}</option>
          {inputs.events.map((e) => (
            <option key={e.public_id} value={e.public_id}>
              {e.starts_at.slice(0, 10)} · {e.name}
            </option>
          ))}
        </select>
      </Label>
      {event ? (
        <p className="text-small">
          <Trans>Норма новых смен: {inputs.settings.norm_hours} ч.</Trans>{' '}
          {new Date(event.starts_at).toLocaleTimeString('ru', {
            timeZone: inputs.timezone,
            hour: '2-digit',
            minute: '2-digit',
          })}
          –
          {new Date(event.ends_at).toLocaleTimeString('ru', {
            timeZone: inputs.timezone,
            hour: '2-digit',
            minute: '2-digit',
          })}{' '}
          <Trans>по времени события</Trans>
        </p>
      ) : null}
      {existing ? (
        <p className="text-small">
          <Trans>Сохранённое распределение: версия {existing.version}.</Trans>{' '}
          <Button
            onClick={() => {
              changeRaw(existing.raw_text)
              try {
                const rows = teacherWorkStoredRowsSchema.parse(
                  JSON.parse(existing.rows_json) as unknown,
                )
                const p = teacherWorkPreviewSchema.parse({
                  rows: rows.map((r) => ({ ...r, candidates: [] })),
                  notes: [],
                  eventCandidates: [eventId],
                  preliminary: existing.state === 'draft',
                  sourceSha256: '',
                })
                setPreview(p)
              } catch {
                setError(t`Не удалось открыть сохранённое распределение`)
              }
            }}
            variant="link"
          >
            <Trans>Открыть для правки</Trans>
          </Button>
        </p>
      ) : null}
      {preview ? (
        <>
          <p className="text-small">
            {preview.preliminary
              ? t`Предварительное распределение: сохраните черновик либо подтвердите фактические смены.`
              : t`Проверьте преподавателей и исключения времени перед подтверждением.`}
          </p>
          <p className="text-small" role="status">
            <Trans>
              Выбрано: {preview.rows.filter((r) => r.teacherId).length} из {preview.rows.length}.
            </Trans>{' '}
            <Trans>Однозначные соответствия заполнены. Подтвердите состав после проверки.</Trans>
          </p>
          <Label className="flex items-center gap-2">
            <Checkbox
              checked={needsChoiceOnly}
              onCheckedChange={(v) => setNeedsChoiceOnly(v === true)}
            />
            <Trans>Только требуют выбора</Trans>
          </Label>
          {unmatchedCount > 0 ? (
            <Button
              onClick={() =>
                setPreview({
                  ...preview,
                  rows: preview.rows.filter((r) => r.teacherId || r.candidates.length > 0),
                })
              }
              size="sm"
              variant="outline"
            >
              <Trans>Исключить все без совпадений ({unmatchedCount})</Trans>
            </Button>
          ) : null}
          <div className="overflow-x-auto">
            <table className="teacher-work-inputs">
              <caption className="sr-only">
                <Trans>Предварительный просмотр смен</Trans>
              </caption>
              <thead>
                <tr>
                  <th>
                    <Trans>Комната и подпись</Trans>
                  </th>
                  <th>
                    <Trans>Преподаватель</Trans>
                  </th>
                  <th>
                    <Trans>С</Trans>
                  </th>
                  <th>
                    <Trans>До</Trans>
                  </th>
                  <th>
                    <Trans>Часы</Trans>
                  </th>
                  <th>
                    <Trans>Строка источника</Trans>
                  </th>
                  <th>
                    <Trans>Действие</Trans>
                  </th>
                </tr>
              </thead>
              <tbody>
                {preview.rows
                  .filter((row) => !needsChoiceOnly || !row.teacherId)
                  .map((row) => (
                    <tr key={row.rowId}>
                      <th scope="row">
                        {row.room} · {row.name}
                      </th>
                      <td>
                        <TeacherSelect
                          label={t`Преподаватель для ${row.name}`}
                          onChange={(id) =>
                            update(row.rowId, {
                              teacherId: id,
                              matchKind: id ? 'manual' : 'unresolved',
                            })
                          }
                          teachers={teachers}
                          value={row.teacherId}
                        />
                        <div className="text-caption text-muted-foreground">
                          {row.teacherId
                            ? row.matchKind === 'exact'
                              ? t`Точное соответствие`
                              : row.matchKind === 'remembered'
                                ? t`Ранее подтверждено`
                                : t`Выбрано вручную`
                            : row.matchKind === 'ambiguous'
                              ? t`Несколько совпадений — выберите преподавателя`
                              : row.candidates.length
                                ? t`Похожее имя — проверьте подсказку`
                                : t`Не найден — выберите или исключите`}
                        </div>
                        {!row.teacherId ? (
                          <div className="flex flex-wrap gap-1">
                            {row.candidates.map((candidate) => (
                              <Button
                                key={candidate.teacherId}
                                aria-label={t`Выбрать ${candidate.label} для ${row.name}`}
                                onClick={() =>
                                  update(row.rowId, {
                                    teacherId: candidate.teacherId,
                                    matchKind: 'manual',
                                  })
                                }
                                size="sm"
                                variant="outline"
                              >
                                {candidate.label}
                              </Button>
                            ))}
                          </div>
                        ) : null}
                      </td>
                      <td>
                        <Input
                          aria-label={t`Начало для ${row.name}`}
                          onChange={(e) =>
                            update(row.rowId, { startsTime: e.target.value || null })
                          }
                          type="time"
                          value={row.startsTime ?? ''}
                        />
                      </td>
                      <td>
                        <Input
                          aria-label={t`Окончание для ${row.name}`}
                          onChange={(e) => update(row.rowId, { endsTime: e.target.value || null })}
                          type="time"
                          value={row.endsTime ?? ''}
                        />
                      </td>
                      <td>{h(credited(row))}</td>
                      <td className="max-w-64 break-words">{row.source}</td>
                      <td>
                        <Button
                          aria-label={t`Исключить ${row.name}`}
                          onClick={() =>
                            setPreview({
                              ...preview,
                              rows: preview.rows.filter((r) => r.rowId !== row.rowId),
                            })
                          }
                          size="sm"
                          variant="ghost"
                        >
                          <Trans>Исключить</Trans>
                        </Button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="text-small">
            <Trans>
              Комнаты одного преподавателя объединяются в одну смену. Разные исключения времени
              нужно исправить.
            </Trans>
          </p>
          <details>
            <summary>
              <Trans>Комментарии и резерв</Trans>
            </summary>
            <ul>
              {preview.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </details>
          <Label className="flex items-center gap-2">
            <Checkbox checked={replace} onCheckedChange={(v) => setReplace(v === true)} />
            <Trans>
              Заменить состав события: удалить прежние смены отсутствующих преподавателей
            </Trans>
          </Label>
          <div className="flex flex-wrap gap-2">
            <Button disabled={saving || !event} onClick={() => save('draft')} variant="outline">
              <Trans>Сохранить черновик</Trans>
            </Button>
            <Button
              disabled={
                saving ||
                !event ||
                !base ||
                conflict ||
                preview.rows.some((r) => !r.teacherId || credited(r) === null)
              }
              onClick={() => save('confirmed')}
            >
              <Trans>Подтвердить фактические смены</Trans>
            </Button>
          </div>
        </>
      ) : null}
      <h2 className="text-subtitle">
        <Trans>Сохранённые распределения</Trans>
      </h2>
      <ul>
        {inputs.rosters.map((r) => (
          <li key={r.eventPublicId}>
            <Button
              onClick={() => {
                bindEvent(r.eventPublicId)
                changeRaw(r.raw_text)
              }}
              variant="link"
            >
              {inputs.events.find((e) => e.public_id === r.eventPublicId)?.starts_at.slice(0, 10)} ·{' '}
              {r.state === 'draft' ? t`Черновик` : t`Подтверждено`} · {r.version}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SettingsView({
  inputs,
  saving,
  onSave,
}: {
  inputs: TeacherWorkInputs
  saving: boolean
  onSave: Save
}) {
  const [norm, setNorm] = useState(String(inputs.settings.norm_hours))
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault()
        onSave({
          action: 'settings',
          normHours: Number(norm),
          expectedVersion: inputs.settings.version,
        })
      }}
    >
      <Label className="grid max-w-sm gap-1">
        <Trans>Стандартное время очной смены, ч</Trans>
        <Input
          max={24}
          min={0}
          onChange={(e) => setNorm(e.target.value)}
          required
          step="0.1"
          type="number"
          value={norm}
        />
      </Label>
      <p className="text-small">
        <Trans>
          Изменение нормы применяется к новым подтверждаемым сменам. Уже подтверждённые смены
          сохраняют свою норму и границы времени. Исключения «с» и «до» добавляют или вычитают
          фактическую разницу.
        </Trans>
      </p>
      <Button disabled={saving} type="submit">
        <Trans>Сохранить норму</Trans>
      </Button>
      <p className="text-small">
        <Trans>
          Учёт обновляется каждые два часа и по кнопке. Письменная работа учитывается по занятию
          задачи, приём — по фактической дате. Ручная поправка задаёт итоговое число часов.
        </Trans>
      </p>
    </form>
  )
}

function DetailView({
  details,
  saving,
  onSave,
}: {
  details: TeacherWorkDetails
  saving: boolean
  onSave: Save
}) {
  const [value, setValue] = useState(String(details.override?.hours ?? details.cell.hours ?? ''))
  const [comment, setComment] = useState(details.override?.comment ?? '')
  const stale = details.override && details.override.source_fingerprint !== details.cell.fingerprint
  return (
    <div className="space-y-3">
      <p>
        {details.cell.slot} · {sourceName(details.cell.source)} · {h(details.cell.hours, 2)}{' '}
        <Trans>ч</Trans>
      </p>
      {stale ? (
        <p className="text-status-warning" role="status">
          <Trans>Требует повторной проверки: источник изменился, ручное время сохранено.</Trans>
        </p>
      ) : null}
      <Evidence details={details} />
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          onSave({
            action: 'override',
            cellKey: details.cell.key,
            hours: Number(value),
            comment,
            sourceFingerprint: details.cell.fingerprint,
            expectedVersion: details.override?.version ?? 0,
          })
        }}
      >
        <Label className="grid gap-1">
          <Trans>Итоговые часы вручную</Trans>
          <Input
            min={0}
            onChange={(e) => setValue(e.target.value)}
            required
            step="0.01"
            type="number"
            value={value}
          />
        </Label>
        <Label className="grid gap-1">
          <Trans>Причина поправки</Trans>
          <Textarea
            maxLength={2000}
            onChange={(e) => setComment(e.target.value)}
            required
            value={comment}
          />
        </Label>
        <div className="flex flex-wrap gap-2">
          <Button disabled={saving || !comment.trim()} type="submit">
            <Trans>Сохранить поправку</Trans>
          </Button>
          {details.override && details.override.hours !== null ? (
            <Button
              disabled={saving || !comment.trim()}
              onClick={() =>
                onSave({
                  action: 'override',
                  cellKey: details.cell.key,
                  hours: null,
                  comment,
                  sourceFingerprint: details.cell.fingerprint,
                  expectedVersion: details.override!.version,
                })
              }
              variant="outline"
            >
              <Trans>Вернуть расчётное время</Trans>
            </Button>
          ) : null}
        </div>
      </form>
      <details>
        <summary>
          <Trans>История правок</Trans>
        </summary>
        {details.audit.map((a, i) => (
          <p key={i}>
            {a.created_at} · {a.surname} {a.name}
          </p>
        ))}
      </details>
    </div>
  )
}

function scalar(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

function Evidence({ details }: { details: TeacherWorkDetails }) {
  // Variable provenance is validated for rendering; raw technical JSON stays out of the UI.
  const evidence = details.cell.evidence
  if (details.cell.kind === 'written' && Array.isArray(evidence))
    return (
      <div className="max-h-56 overflow-auto">
        <p>
          <Trans>Проверок: {evidence.length}</Trans>
        </p>
        <ul>
          {evidence.map((row: unknown, index) => {
            if (!row || typeof row !== 'object') return null
            const r = row as Record<string, unknown>
            return (
              <li key={index}>
                {scalar(r.ts)} · <Trans>Задача</Trans> {scalar(r.problem_id)} ·{' '}
                <Trans>Вердикт</Trans> {scalar(r.verdict)} · {scalar(r.seconds)} <Trans>с</Trans> ·{' '}
                {sourceName(scalar(r.source))}
              </li>
            )
          })}
        </ul>
      </div>
    )
  if (details.cell.kind === 'school' && Array.isArray(evidence))
    return (
      <ul>
        {evidence.map((row: unknown, index) => {
          if (!row || typeof row !== 'object') return null
          const r = row as Record<string, unknown>
          return (
            <li key={index}>
              {scalar(r.starts_at)} — {scalar(r.ends_at)} · <Trans>Норма</Trans>{' '}
              {scalar(r.norm_hours)} <Trans>ч</Trans>
            </li>
          )
        })}
      </ul>
    )
  if (details.cell.kind === 'zoom')
    return (
      <p className="text-small">
        {details.cell.anomalies.length
          ? t`Лог неполный или неоднозначный. При наличии устных результатов весь день заменяется оценкой: не более 3.5 ч, максимум из интервала проверок + 0.3 ч и количества проверок / 14.`
          : t`Время по парным входам и выходам. Пересекающиеся подключения объединены.`}
      </p>
    )
  return null
}

export function TeacherWorkPage({
  onSectionChange,
  search,
  onSearchChange,
}: {
  onSectionChange: (section: UsersSection) => void
  search: WorkSearch
  onSearchChange: (search: WorkSearch) => void
}) {
  const auth = useAuthentication(),
    principal = useAuthenticatedPrincipal(),
    queryClient = useQueryClient()
  const admin = principal.audience === 'staff' && principal.role === 'admin'
  const client = useMemo(
    () => createTeacherWorkClient(auth.client.runtime, () => auth.refresh()),
    [auth],
  )
  const scope = [...principalQueryKey(principal), 'teacher-work']
  const catalog = useQuery({
    queryKey: [...scope, 'catalog'],
    queryFn: ({ signal }) => client.catalog(signal),
    enabled: admin,
  })
  const courseId =
    search.course ??
    catalog.data?.courses.find((c) => c.status === 'active')?.courseId ??
    catalog.data?.courses[0]?.courseId ??
    ''
  const section = search.section ?? 'report'
  const report = useQuery({
    queryKey: [...scope, 'report', courseId, search.first, search.last, search.q],
    queryFn: ({ signal }) =>
      client.report(courseId, { first: search.first, last: search.last, q: search.q }, signal),
    enabled: admin && !!courseId,
    refetchInterval: (query) =>
      ['queued', 'running'].includes(query.state.data?.operation?.state ?? '') ? 1500 : 30000,
  })
  const inputs = useQuery({
    queryKey: [...scope, 'inputs', courseId],
    queryFn: ({ signal }) => client.inputs(courseId, signal),
    enabled: admin && !!courseId && section !== 'report',
  })
  const [selected, setSelected] = useState<string | null>(null)
  const details = useQuery({
    queryKey: [...scope, 'details', courseId, selected],
    queryFn: ({ signal }) => client.details(courseId, selected!, signal),
    enabled: admin && !!courseId && !!selected,
  })
  const lastCommand = useRef<{ payload: string; key: string } | null>(null)
  const mutation = useMutation({
    mutationFn: (input: Parameters<Save>[0]) => {
      const payload = JSON.stringify({ courseId, ...input })
      const key =
        lastCommand.current?.payload === payload ? lastCommand.current.key : crypto.randomUUID()
      lastCommand.current = { payload, key }
      return client.command({ ...input, courseId, idempotencyKey: key })
    },
    onSuccess: async (receipt, input) => {
      lastCommand.current = null
      if (input.action === 'alias' && receipt.alias) {
        // A background read begun before the write must not restore an older alias.
        await queryClient.cancelQueries({ queryKey: [...scope, 'inputs', courseId] })
        queryClient.setQueryData<TeacherWorkInputs>([...scope, 'inputs', courseId], (current) =>
          acceptAliasReceipt(current, receipt, input.name),
        )
      } else {
        void queryClient.invalidateQueries({ queryKey: [...scope, 'inputs', courseId] })
        if (input.action === 'override') {
          void queryClient.invalidateQueries({ queryKey: [...scope, 'report', courseId] })
          void queryClient.invalidateQueries({ queryKey: [...scope, 'details', courseId] })
        }
      }
    },
    onError: (error) => auth.handleApiError(error),
  })
  const runKey = useRef<string | null>(null)
  const recalc = useMutation({
    mutationFn: () => {
      runKey.current ??= crypto.randomUUID()
      return client.recalculate(courseId, runKey.current)
    },
    onSuccess: () => {
      runKey.current = null
      void queryClient.invalidateQueries({ queryKey: scope })
    },
    onError: (error) => auth.handleApiError(error),
  })
  const busy =
    ['queued', 'running'].includes(report.data?.operation?.state ?? '') || recalc.isPending
  function change(patch: Partial<WorkSearch>) {
    onSearchChange({ ...search, course: courseId, ...patch })
  }
  let content: ReactNode
  const active = section === 'report' ? report : inputs
  if (!admin)
    content = (
      <PageStatePanel
        state="forbidden"
        description={t`Учёт работы доступен только администратору.`}
      />
    )
  else if (!catalog.isPending && !catalog.error && !courseId)
    content = <PageStatePanel state="empty" title={t`Курсов пока нет`} />
  else if (catalog.isPending || active.isPending) content = <PageStatePanel state="loading" />
  else if (catalog.error || active.error)
    content = (
      <PageStatePanel
        actionLabel={t`Повторить`}
        onAction={() => void queryClient.invalidateQueries({ queryKey: scope })}
        state={
          (catalog.error instanceof ApiResponseError && catalog.error.status === 403) ||
          (active.error instanceof ApiResponseError && active.error.status === 403)
            ? 'forbidden'
            : 'error'
        }
      />
    )
  else if (!courseId) content = <PageStatePanel state="empty" title={t`Курсов пока нет`} />
  else if (section === 'report' && report.data)
    content = <TeacherWorkReportView onCell={setSelected} report={report.data} />
  else if (inputs.data && catalog.data)
    content =
      section === 'zoom' ? (
        <ZoomView
          inputs={inputs.data}
          onCell={setSelected}
          onSave={(v) => mutation.mutate(v)}
          report={report.data}
          saving={mutation.isPending}
          teachers={catalog.data.teachers}
        />
      ) : section === 'school' ? (
        <TeacherWorkRosterView
          draftKey={`${auth.client.runtime.instance}:${principal.accountId}:${courseId}:teacher-work-roster`}
          inputs={inputs.data}
          key={courseId}
          onPreview={(text) => client.preview(courseId, text)}
          onSave={(v, onSuccess) =>
            mutation.mutate(v, { onSuccess: (receipt) => onSuccess?.(receipt) })
          }
          saving={mutation.isPending}
          teachers={catalog.data.teachers}
        />
      ) : (
        <SettingsView
          inputs={inputs.data}
          key={`${courseId}:${inputs.data.settings.version}`}
          onSave={(v) => mutation.mutate(v)}
          saving={mutation.isPending}
        />
      )
  return (
    <PageLayout
      description={t`Очные смены, Zoom-приём и письменная проверка`}
      title={t`Участники и группы`}
      width="wide"
    >
      <div className="space-y-4">
        <UsersSectionTabs
          onChange={onSectionChange}
          section="work"
          showImports={admin}
          showTeachers={admin}
          showWork={admin}
        />
        {admin ? (
          <>
            <div className="max-w-full overflow-x-auto pb-2">
              <Tabs
                onValueChange={(value) => change({ section: value as WorkSection })}
                value={section}
              >
                <TabsList aria-label={t`Раздел учёта работы`} variant="line">
                  <TabsTrigger value="report">
                    <Trans>Отчёт</Trans>
                  </TabsTrigger>
                  <TabsTrigger value="school">
                    <Trans>Очные смены</Trans>
                  </TabsTrigger>
                  <TabsTrigger value="zoom">Zoom</TabsTrigger>
                  <TabsTrigger value="settings">
                    <Trans>Настройки</Trans>
                  </TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
            <div className="flex flex-wrap items-end gap-3">
              <Label className="grid gap-1">
                <Trans>Курс</Trans>
                <select
                  className={selectClass}
                  onChange={(e) => {
                    setSelected(null)
                    onSearchChange({ section, course: e.target.value })
                  }}
                  value={courseId}
                >
                  {catalog.data?.courses.map((c) => (
                    <option key={c.courseId} value={c.courseId}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Label>
              {section === 'report' ? (
                <>
                  <Label className="grid gap-1">
                    <Trans>С занятия</Trans>
                    <Input
                      className="w-24"
                      min={0}
                      onChange={(e) =>
                        change({ first: e.target.value ? Number(e.target.value) : undefined })
                      }
                      type="number"
                      value={search.first ?? ''}
                    />
                  </Label>
                  <Label className="grid gap-1">
                    <Trans>По занятие</Trans>
                    <Input
                      className="w-24"
                      min={0}
                      onChange={(e) =>
                        change({ last: e.target.value ? Number(e.target.value) : undefined })
                      }
                      type="number"
                      value={search.last ?? ''}
                    />
                  </Label>
                  <Label className="grid gap-1">
                    <Trans>Поиск преподавателя</Trans>
                    <Input
                      maxLength={100}
                      onChange={(e) => change({ q: e.target.value })}
                      value={search.q ?? ''}
                    />
                  </Label>
                </>
              ) : null}
              <Button
                disabled={busy || !courseId}
                onClick={() => recalc.mutate()}
                variant="outline"
              >
                {busy ? t`Пересчитываем…` : t`Пересчитать учёт`}
              </Button>
            </div>
            <p className="text-caption text-muted-foreground" role="status">
              {busy
                ? t`Расчёт выполняется. Можно покинуть страницу.`
                : report.data?.operation?.state === 'failed'
                  ? t`Пересчёт не завершён. Прежний отчёт сохранён.`
                  : report.data?.run?.completedAt
                    ? t`Обновлено: ${report.data.run.completedAt}`
                    : null}
            </p>
          </>
        ) : null}
        {mutation.error || recalc.error ? (
          <p className="text-status-error" role="alert">
            {t`Не удалось сохранить или запустить расчёт. Данные могли измениться. Обновите страницу и повторите запрос.`}{' '}
            <Button
              onClick={() => void queryClient.invalidateQueries({ queryKey: scope })}
              variant="link"
            >
              <Trans>Обновить данные</Trans>
            </Button>
          </p>
        ) : null}
        {content}
        <Dialog
          onOpenChange={(open) => {
            if (!open) setSelected(null)
          }}
          open={!!selected}
        >
          <DialogContent className="max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                <Trans>Подробности работы</Trans>
              </DialogTitle>
              <DialogDescription>
                <Trans>Источник времени и ручная поправка</Trans>
              </DialogDescription>
            </DialogHeader>
            {details.isPending ? (
              <PageStatePanel state="loading" />
            ) : details.error ? (
              <PageStatePanel
                actionLabel={t`Повторить`}
                onAction={() => void details.refetch()}
                state="error"
              />
            ) : details.data ? (
              <DetailView
                details={details.data}
                key={`${details.data.cell.fingerprint}:${details.data.override?.version ?? 0}`}
                onSave={(v) => mutation.mutate(v)}
                saving={mutation.isPending}
              />
            ) : null}
          </DialogContent>
        </Dialog>
      </div>
    </PageLayout>
  )
}
