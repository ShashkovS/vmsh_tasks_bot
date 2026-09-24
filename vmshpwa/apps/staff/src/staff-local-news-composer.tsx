import type { AdminCourse, RichDocument } from '@vmsh/contracts'
import { lazy, Suspense, useState } from 'react'

import { Button, Input, Label } from '@vmsh/ui'

import type { LocalNewsDraft } from './local-news-draft'

const RichMarkdownEditor = lazy(() =>
  import('./rich-markdown-editor').then((module) => ({ default: module.RichMarkdownEditor })),
)

function moscowNowInput(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: 'Europe/Moscow',
  }).formatToParts(new Date())
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((value) => value.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`
}

export function StaffLocalNewsComposer({
  courses,
  draft,
  pending = false,
  targetDisabled = false,
  publishedAtDisabled = false,
  submitLabel = 'Запланировать публикацию',
  onChange,
  onImageUpload,
  onSubmit,
}: {
  courses: AdminCourse[]
  draft: LocalNewsDraft
  pending?: boolean
  targetDisabled?: boolean
  publishedAtDisabled?: boolean
  submitLabel?: string
  onChange: (draft: LocalNewsDraft) => void
  onImageUpload?: (image: File) => Promise<{ url: string }>
  onSubmit: (document: RichDocument, courseId: string) => void
}) {
  const [document, setDocument] = useState<RichDocument | null>(null)
  const activeCourses = courses.filter((course) => course.status === 'active')
  const legacyGroupCourseId = activeCourses.find((course) =>
    course.groups.some((group) => group.groupId === draft.groupId),
  )?.courseId
  const courseId = draft.courseId || legacyGroupCourseId || activeCourses[0]?.courseId || ''
  const selectedCourse = activeCourses.find((course) => course.courseId === courseId)
  const valid = courseId !== '' && document !== null && draft.publishedLocal !== ''
  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid && document) onSubmit(document, courseId)
      }}
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Label className="grid gap-1.5" htmlFor="local-news-course">
          Курс
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={targetDisabled}
            id="local-news-course"
            onChange={(event) => onChange({ ...draft, courseId: event.target.value, groupId: '' })}
            required
            value={courseId}
          >
            {activeCourses.map((course) => (
              <option key={course.courseId} value={course.courseId}>
                {course.name}
              </option>
            ))}
          </select>
        </Label>
        <Label className="grid gap-1.5" htmlFor="local-news-group">
          Группа
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={targetDisabled}
            id="local-news-group"
            onChange={(event) => onChange({ ...draft, groupId: event.target.value })}
            value={draft.groupId}
          >
            <option value="">Все</option>
            {selectedCourse?.groups
              .filter((group) => group.status === 'active')
              .map((group) => (
                <option key={group.groupId} value={group.groupId}>
                  {group.name}
                </option>
              ))}
          </select>
        </Label>
        <Label className="grid gap-1.5" htmlFor="local-news-audience">
          Показывать
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={targetDisabled}
            id="local-news-audience"
            onChange={(event) =>
              onChange({
                ...draft,
                audience: event.target.value as LocalNewsDraft['audience'],
              })
            }
            value={draft.audience}
          >
            <option value="both">Всем</option>
            <option value="student">Только школьнику</option>
            <option value="family">Только родителям</option>
          </select>
        </Label>
        <Label className="grid gap-1.5" htmlFor="local-news-attendance">
          Очность
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={targetDisabled}
            id="local-news-attendance"
            onChange={(event) =>
              onChange({
                ...draft,
                attendanceMode: event.target.value as LocalNewsDraft['attendanceMode'],
              })
            }
            value={draft.attendanceMode}
          >
            <option value="all">Всем</option>
            <option value="in_person">Только очные</option>
            <option value="online">Только онлайн</option>
          </select>
        </Label>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="local-news-editor">Текст публикации (Markdown)</Label>
        <Suspense
          fallback={
            <div className="min-h-[22rem] rounded-md border border-border p-3 text-caption text-muted-foreground">
              Загружаем редактор…
            </div>
          }
        >
          <RichMarkdownEditor
            id="local-news-editor"
            onChange={(text) => onChange({ ...draft, text })}
            onDocumentChange={setDocument}
            {...(onImageUpload === undefined ? {} : { onImageUpload })}
            value={draft.text}
          />
        </Suspense>
      </div>
      <div className="grid gap-1.5">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="local-news-published-at">
            {publishedAtDisabled
              ? 'Опубликовано по московскому времени'
              : 'Опубликовать по московскому времени'}
          </Label>
          {!publishedAtDisabled ? (
            <Button
              onClick={() => onChange({ ...draft, publishedLocal: moscowNowInput() })}
              size="sm"
              type="button"
              variant="outline"
            >
              Сейчас
            </Button>
          ) : null}
        </div>
        <Input
          aria-label={
            publishedAtDisabled
              ? 'Опубликовано по московскому времени'
              : 'Опубликовать по московскому времени'
          }
          disabled={publishedAtDisabled}
          id="local-news-published-at"
          onChange={(event) => onChange({ ...draft, publishedLocal: event.target.value })}
          required
          type="datetime-local"
          value={draft.publishedLocal}
        />
      </div>
      <p className="text-caption text-muted-foreground">
        Сохранение доступно только после строгой проверки Markdown. Внешние картинки копируются на
        сервер при сохранении.
      </p>
      <Button disabled={!valid || pending} type="submit">
        {pending ? 'Сохраняем…' : submitLabel}
      </Button>
    </form>
  )
}
