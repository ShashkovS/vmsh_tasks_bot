import { useState, type FormEvent } from 'react'

import type {
  SaveAdminCourseScheduleRule,
  SaveAdminGroupScheduleOverride,
  ScheduleField,
  ScheduleOverrideMode,
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

import { scheduleFieldLabels } from './course-schedule-draft'

interface Draft {
  mode: ScheduleOverrideMode
  dayOffset: string
  localTime: string
  timezone: string
}

function readDraft(storageKey: string, fallback: Draft): Draft {
  try {
    const value: unknown = JSON.parse(globalThis.localStorage.getItem(storageKey) ?? 'null')
    if (!value || typeof value !== 'object') return fallback
    const stored = value as Partial<Draft>
    return {
      mode:
        stored.mode === 'inherit' || stored.mode === 'override' || stored.mode === 'disabled'
          ? stored.mode
          : fallback.mode,
      dayOffset: typeof stored.dayOffset === 'string' ? stored.dayOffset : fallback.dayOffset,
      localTime: typeof stored.localTime === 'string' ? stored.localTime : fallback.localTime,
      timezone: typeof stored.timezone === 'string' ? stored.timezone : fallback.timezone,
    }
  } catch {
    return fallback
  }
}

export function CourseScheduleEditor({
  field,
  initial,
  mode,
  open,
  saving,
  storageKey,
  onOpenChange,
  onSave,
}: {
  field: ScheduleField
  initial?: { dayOffset: number; localTime: string; timezone: string }
  mode?: ScheduleOverrideMode
  open: boolean
  saving: boolean
  storageKey: string
  onOpenChange: (open: boolean) => void
  onSave: (input: SaveAdminCourseScheduleRule | SaveAdminGroupScheduleOverride) => void
}) {
  const groupOverride = mode !== undefined
  const fallback: Draft = {
    mode: mode ?? 'override',
    dayOffset: String(initial?.dayOffset ?? 0),
    localTime: (initial?.localTime ?? '16:30').slice(0, 5),
    timezone: initial?.timezone ?? 'Europe/Moscow',
  }
  const [draft, setDraft] = useState(() => readDraft(storageKey, fallback))
  const [storageAvailable, setStorageAvailable] = useState(true)

  function update(update: Partial<Draft>) {
    const next = { ...draft, ...update }
    setDraft(next)
    try {
      globalThis.localStorage.setItem(storageKey, JSON.stringify(next))
      setStorageAvailable(true)
    } catch {
      setStorageAvailable(false)
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (groupOverride) {
      const hasValue = draft.mode === 'override'
      onSave({
        schemaVersion: 1,
        field,
        mode: draft.mode,
        dayOffset: hasValue ? Number(draft.dayOffset) : null,
        localTime: hasValue ? draft.localTime : null,
        timezone: hasValue ? draft.timezone : null,
      })
      return
    }
    onSave({
      schemaVersion: 1,
      field,
      dayOffset: Number(draft.dayOffset),
      localTime: draft.localTime,
      timezone: draft.timezone,
    })
  }

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{scheduleFieldLabels[field]}</DialogTitle>
          <DialogDescription>
            Время задаётся относительно даты начала цикла и сохраняется в часовом поясе курса.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-3" onSubmit={submit}>
          {groupOverride ? (
            <Label className="grid gap-1">
              Режим
              <select
                className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                disabled={saving}
                onChange={(event) => update({ mode: event.target.value as ScheduleOverrideMode })}
                value={draft.mode}
              >
                <option value="inherit">Как в курсе</option>
                <option value="override">Своё время</option>
                {field === 'submission_closes_at' ? null : (
                  <option value="disabled">Не использовать</option>
                )}
              </select>
            </Label>
          ) : null}
          {!groupOverride || draft.mode === 'override' ? (
            <>
              <Label className="grid gap-1">
                Смещение в днях
                <Input
                  disabled={saving}
                  max={30}
                  min={-30}
                  onChange={(event) => update({ dayOffset: event.target.value })}
                  required
                  type="number"
                  value={draft.dayOffset}
                />
              </Label>
              <Label className="grid gap-1">
                Время
                <Input
                  disabled={saving}
                  onChange={(event) => update({ localTime: event.target.value })}
                  required
                  type="time"
                  value={draft.localTime}
                />
              </Label>
              <Label className="grid gap-1">
                Часовой пояс
                <Input
                  disabled={saving}
                  onChange={(event) => update({ timezone: event.target.value })}
                  required
                  value={draft.timezone}
                />
              </Label>
            </>
          ) : null}
          {!storageAvailable ? (
            <p className="text-small text-status-error" role="alert">
              Черновик не сохраняется в этом браузере. Не закрывайте вкладку до отправки.
            </p>
          ) : null}
          <DialogFooter>
            <Button disabled={saving} type="submit">
              {saving ? 'Сохраняем…' : 'Показать изменения'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
