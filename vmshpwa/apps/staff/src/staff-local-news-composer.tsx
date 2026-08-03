import type { AdminCourse } from '@vmsh/contracts'
import { Button, Input, Label, Textarea } from '@vmsh/ui'

import type { LocalNewsDraft } from './local-news-draft'

export function StaffLocalNewsComposer({
  courses,
  draft,
  pending = false,
  ownerDisabled = false,
  publishedAtDisabled = false,
  submitLabel = 'Запланировать публикацию',
  onChange,
  onSubmit,
}: {
  courses: AdminCourse[]
  draft: LocalNewsDraft
  pending?: boolean
  ownerDisabled?: boolean
  publishedAtDisabled?: boolean
  submitLabel?: string
  onChange: (draft: LocalNewsDraft) => void
  onSubmit: () => void
}) {
  const valid = draft.owner !== '' && draft.text.trim() !== '' && draft.publishedLocal !== ''
  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid) onSubmit()
      }}
    >
      <Label className="grid gap-1.5" htmlFor="local-news-owner">
        Кому показать
        <select
          className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
          disabled={ownerDisabled}
          id="local-news-owner"
          onChange={(event) => onChange({ ...draft, owner: event.target.value })}
          required
          value={draft.owner}
        >
          <option value="">Выберите курс или группу</option>
          {courses
            .filter((course) => course.status === 'active')
            .map((course) => (
              <optgroup key={course.courseId} label={course.name}>
                <option value={`course:${course.courseId}`}>Весь курс</option>
                {course.groups
                  .filter((group) => group.status === 'active')
                  .map((group) => (
                    <option key={group.groupId} value={`group:${group.groupId}`}>
                      {group.name}
                    </option>
                  ))}
              </optgroup>
            ))}
        </select>
      </Label>
      <Label className="grid gap-1.5" htmlFor="local-news-text">
        Текст публикации
        <Textarea
          id="local-news-text"
          maxLength={32_768}
          onChange={(event) => onChange({ ...draft, text: event.target.value })}
          placeholder="Короткое сообщение для ленты PWA"
          required
          rows={7}
          value={draft.text}
        />
      </Label>
      <Label className="grid gap-1.5" htmlFor="local-news-published-at">
        {publishedAtDisabled
          ? 'Опубликовано по московскому времени'
          : 'Опубликовать по московскому времени'}
        <Input
          disabled={publishedAtDisabled}
          id="local-news-published-at"
          onChange={(event) => onChange({ ...draft, publishedLocal: event.target.value })}
          required
          type="datetime-local"
          value={draft.publishedLocal}
        />
      </Label>
      <p className="text-caption text-muted-foreground">
        В первой версии поддерживается обычный текст. Полный Markdown-редактор появится во второй
        фазе.
      </p>
      <Button disabled={!valid || pending} type="submit">
        {pending ? 'Сохраняем…' : submitLabel}
      </Button>
    </form>
  )
}
