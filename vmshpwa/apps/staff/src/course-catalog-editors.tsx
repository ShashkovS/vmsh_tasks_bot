import { useState, type FormEvent } from 'react'

import type {
  AdminCourse,
  AdminGroup,
  CatalogStatus,
  SaveAdminGroupRequest,
  UpdateAdminCourseRequest,
} from '@vmsh/contracts'
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Label,
} from '@vmsh/ui'

interface CourseDraft {
  code: string
  name: string
  subjectCode: string
  status: CatalogStatus
  sortOrder: string
  accentKey: string
}

interface GroupDraft {
  shortCode: string
  name: string
  status: CatalogStatus
  colorKey: string
  sortOrder: string
  allowSelfSwitch: boolean
  scoreWeight: string
}

function readDraft<T extends CourseDraft | GroupDraft>(key: string, fallback: T): T {
  try {
    const value: unknown = JSON.parse(globalThis.localStorage.getItem(key) ?? 'null')
    if (!value || typeof value !== 'object') return fallback
    const stored = value as Partial<T>
    const result = { ...fallback }
    for (const field of Object.keys(fallback) as Array<keyof T>) {
      if (typeof stored[field] === typeof fallback[field])
        result[field] = stored[field] as T[keyof T]
    }
    return result
  } catch {
    return fallback
  }
}

function writeDraft(key: string, draft: CourseDraft | GroupDraft): boolean {
  try {
    globalThis.localStorage.setItem(key, JSON.stringify(draft))
    return true
  } catch {
    return false
  }
}

function statusSelect(
  value: CatalogStatus,
  setValue: (value: CatalogStatus) => void,
  disabled: boolean,
) {
  return (
    <Label className="grid gap-1">
      Состояние
      <select
        className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
        disabled={disabled}
        onChange={(event) => setValue(event.target.value as CatalogStatus)}
        value={value}
      >
        <option value="draft">Черновик</option>
        <option value="active">Активен</option>
        <option value="archived">В архиве</option>
      </select>
    </Label>
  )
}

export function CourseCatalogEditor({
  course,
  open,
  saving,
  storageKey,
  onOpenChange,
  onSave,
}: {
  course: AdminCourse | null
  open: boolean
  saving: boolean
  storageKey: string
  onOpenChange: (open: boolean) => void
  onSave: (request: UpdateAdminCourseRequest) => void
}) {
  const fallback: CourseDraft = course
    ? {
        code: course.code,
        name: course.name,
        subjectCode: course.subjectCode,
        status: course.status,
        sortOrder: String(course.sortOrder),
        accentKey: course.accentKey,
      }
    : {
        code: '',
        name: '',
        subjectCode: '',
        status: 'draft',
        sortOrder: '0',
        accentKey: 'course',
      }
  const [draft, setDraft] = useState(() => readDraft(storageKey, fallback))
  const [storageAvailable, setStorageAvailable] = useState(true)

  function updateDraft(update: Partial<CourseDraft>) {
    const next = { ...draft, ...update }
    setDraft(next)
    setStorageAvailable(writeDraft(storageKey, next))
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const common = {
      schemaVersion: 1 as const,
      code: draft.code,
      name: draft.name,
      subjectCode: draft.subjectCode,
      status: draft.status,
      sortOrder: Number(draft.sortOrder),
      accentKey: draft.accentKey,
    }
    onSave(common)
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{course ? 'Настройки курса' : 'Новый курс'}</DialogTitle>
          <DialogDescription>
            Курс объединяет группы одного предмета и хранит общий контекст статистики.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={submit}>
          <Label className="grid gap-1">
            Код
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ code: event.target.value })}
              required
              value={draft.code}
            />
          </Label>
          <Label className="grid gap-1">
            Предмет
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ subjectCode: event.target.value })}
              required
              value={draft.subjectCode}
            />
          </Label>
          <Label className="grid gap-1 sm:col-span-2">
            Название
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ name: event.target.value })}
              required
              value={draft.name}
            />
          </Label>
          {statusSelect(draft.status, (status) => updateDraft({ status }), saving)}
          <Label className="grid gap-1">
            Цветовой ключ
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ accentKey: event.target.value })}
              required
              value={draft.accentKey}
            />
          </Label>
          <Label className="grid gap-1">
            Порядок
            <Input
              disabled={saving}
              inputMode="numeric"
              onChange={(event) => updateDraft({ sortOrder: event.target.value })}
              required
              type="number"
              value={draft.sortOrder}
            />
          </Label>
          {!storageAvailable ? (
            <p className="text-small text-status-error sm:col-span-2" role="alert">
              Черновик не сохраняется в этом браузере. Не закрывайте вкладку до отправки.
            </p>
          ) : null}
          <DialogFooter className="sm:col-span-2">
            <Button disabled={saving} type="submit">
              {saving ? 'Сохраняем…' : 'Сохранить'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function GroupCatalogEditor({
  group,
  open,
  saving,
  storageKey,
  onOpenChange,
  onSave,
}: {
  group: AdminGroup | null
  open: boolean
  saving: boolean
  storageKey: string
  onOpenChange: (open: boolean) => void
  onSave: (request: SaveAdminGroupRequest) => void
}) {
  const fallback: GroupDraft = group
    ? {
        shortCode: group.shortCode,
        name: group.name,
        status: group.status,
        colorKey: group.colorKey ?? 'group',
        sortOrder: String(group.sortOrder),
        allowSelfSwitch: group.allowSelfSwitch,
        scoreWeight: String(group.scoreWeight),
      }
    : {
        shortCode: '',
        name: '',
        status: 'draft',
        colorKey: 'group',
        sortOrder: '0',
        allowSelfSwitch: false,
        scoreWeight: '1',
      }
  const [draft, setDraft] = useState(() => readDraft(storageKey, fallback))
  const [storageAvailable, setStorageAvailable] = useState(true)

  function updateDraft(update: Partial<GroupDraft>) {
    const next = { ...draft, ...update }
    setDraft(next)
    setStorageAvailable(writeDraft(storageKey, next))
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSave({
      schemaVersion: 1,
      shortCode: draft.shortCode,
      name: draft.name,
      status: draft.status,
      colorKey: draft.colorKey,
      sortOrder: Number(draft.sortOrder),
      allowSelfSwitch: draft.allowSelfSwitch,
      scoreWeight: Number(draft.scoreWeight),
    })
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{group ? 'Настройки группы' : 'Новая группа'}</DialogTitle>
          <DialogDescription>
            Название и короткий код должны быть уникальны внутри выбранного курса.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={submit}>
          <Label className="grid gap-1">
            Короткий код
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ shortCode: event.target.value })}
              required
              value={draft.shortCode}
            />
          </Label>
          <Label className="grid gap-1">
            Цветовой ключ
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ colorKey: event.target.value })}
              required
              value={draft.colorKey}
            />
          </Label>
          <Label className="grid gap-1 sm:col-span-2">
            Название
            <Input
              disabled={saving}
              onChange={(event) => updateDraft({ name: event.target.value })}
              required
              value={draft.name}
            />
          </Label>
          {statusSelect(draft.status, (status) => updateDraft({ status }), saving)}
          <Label className="grid gap-1">
            Порядок
            <Input
              disabled={saving}
              inputMode="numeric"
              onChange={(event) => updateDraft({ sortOrder: event.target.value })}
              required
              type="number"
              value={draft.sortOrder}
            />
          </Label>
          <Label className="grid gap-1">
            Вес в статистике
            <Input
              disabled={saving}
              inputMode="decimal"
              max="10"
              min="0.01"
              onChange={(event) => updateDraft({ scoreWeight: event.target.value })}
              required
              step="0.01"
              type="number"
              value={draft.scoreWeight}
            />
          </Label>
          <label className="flex items-center gap-2 self-end text-small font-medium">
            <input
              checked={draft.allowSelfSwitch}
              disabled={saving}
              onChange={(event) => updateDraft({ allowSelfSwitch: event.target.checked })}
              type="checkbox"
            />
            Разрешить самостоятельный переход
          </label>
          {!storageAvailable ? (
            <p className="text-small text-status-error sm:col-span-2" role="alert">
              Черновик не сохраняется в этом браузере. Не закрывайте вкладку до отправки.
            </p>
          ) : null}
          <DialogFooter className="sm:col-span-2">
            <Button disabled={saving} type="submit">
              {saving ? 'Сохраняем…' : 'Сохранить'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
