import { CircleHelp, TriangleAlert } from 'lucide-react'
import { useId, useState } from 'react'

import { Alert, AlertContent, AlertTitle, Button, Checkbox, Label, Textarea, cn } from '@vmsh/ui'

const selectClass =
  'min-h-(--touch-target) w-full rounded-md border border-input bg-surface px-3 text-small text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40'

/* ── Broadcast composer ─────────────────────────────────────────────────── */

export interface AudiencePreset {
  id: string
  label: string
  count: number
}

export interface BroadcastPayload {
  audienceId: string
  text: string
  channels: string[]
  category: string
  quiet: boolean
}

export interface BroadcastComposerProps {
  audiencePresets: AudiencePreset[]
  categories?: { id: string; label: string }[]
  onDryRun?: (payload: BroadcastPayload) => void
  onSend?: (payload: BroadcastPayload) => void
  className?: string
}

export function BroadcastComposer({
  audiencePresets,
  categories = [
    { id: 'important', label: 'Важное' },
    { id: 'news', label: 'Новости' },
  ],
  onDryRun,
  onSend,
  className,
}: BroadcastComposerProps) {
  const audienceId = useId()
  const categoryId = useId()
  const textId = useId()
  const pwaId = useId()
  const tgId = useId()
  const quietId = useId()
  const [audience, setAudience] = useState(audiencePresets[0]?.id ?? '')
  const [text, setText] = useState('')
  const [pwa, setPwa] = useState(true)
  const [telegram, setTelegram] = useState(true)
  const [category, setCategory] = useState(categories[0]?.id ?? '')
  const [quiet, setQuiet] = useState(true)
  const [confirming, setConfirming] = useState(false)

  const count = audiencePresets.find((preset) => preset.id === audience)?.count ?? 0
  const channels = [pwa ? 'pwa' : null, telegram ? 'telegram' : null].filter(Boolean) as string[]
  const payload: BroadcastPayload = { audienceId: audience, text, channels, category, quiet }
  const canSend = text.trim() !== '' && channels.length > 0

  return (
    <div className={cn('max-w-lg space-y-4', className)}>
      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={audienceId}>
          Кому
        </label>
        <select
          className={selectClass}
          id={audienceId}
          onChange={(event) => setAudience(event.target.value)}
          value={audience}
        >
          {audiencePresets.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.label} ({preset.count})
            </option>
          ))}
        </select>
        <p className="text-caption text-muted-foreground" role="status">
          Получат: <span className="font-num font-medium text-foreground">{count}</span>
        </p>
      </div>

      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={textId}>
          Сообщение
        </label>
        <Textarea
          className="min-h-24"
          id={textId}
          onChange={(event) => {
            setText(event.target.value)
            setConfirming(false)
          }}
          value={text}
        />
      </div>

      <fieldset className="space-y-2">
        <legend className="text-label font-medium text-foreground">Куда доставить</legend>
        <div className="flex flex-wrap gap-4">
          <span className="inline-flex items-center gap-2">
            <Checkbox
              checked={pwa}
              id={pwaId}
              onCheckedChange={(value) => setPwa(Boolean(value))}
            />
            <Label htmlFor={pwaId}>В приложении</Label>
          </span>
          <span className="inline-flex items-center gap-2">
            <Checkbox
              checked={telegram}
              id={tgId}
              onCheckedChange={(value) => setTelegram(Boolean(value))}
            />
            <Label htmlFor={tgId}>Telegram</Label>
          </span>
        </div>
      </fieldset>

      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={categoryId}>
          Категория
        </label>
        <select
          className={selectClass}
          id={categoryId}
          onChange={(event) => setCategory(event.target.value)}
          value={category}
        >
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>

      <span className="inline-flex items-center gap-2">
        <Checkbox
          checked={quiet}
          id={quietId}
          onCheckedChange={(value) => setQuiet(Boolean(value))}
        />
        <Label htmlFor={quietId}>Уважать тихие часы</Label>
      </span>

      {confirming ? (
        <div className="space-y-2 rounded-md border border-border bg-surface-subtle p-3 text-small">
          <p className="text-foreground">Отправить {count} получателям?</p>
          <div className="flex gap-2">
            <Button
              onClick={() => {
                onSend?.(payload)
                setConfirming(false)
              }}
              size="sm"
            >
              Отправить
            </Button>
            <Button onClick={() => setConfirming(false)} size="sm" variant="ghost">
              Отмена
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button onClick={() => onDryRun?.(payload)} size="sm" variant="outline">
            Пробный прогон
          </Button>
          <Button disabled={!canSend} onClick={() => setConfirming(true)} size="sm">
            Отправить…
          </Button>
        </div>
      )}
    </div>
  )
}

/* ── Classroom planner ──────────────────────────────────────────────────── */

export interface PlannerRoom {
  id: string
  name: string
  capacity: number
  assigned: string[]
}

export interface ClassroomPlannerProps {
  rooms: PlannerRoom[]
  unassigned: string[]
  conflicts?: string[]
  onMove?: (student: string, toRoomId: string) => void
  className?: string
}

function MoveControl({
  student,
  rooms,
  onMove,
}: {
  student: string
  rooms: PlannerRoom[]
  onMove?: ((student: string, toRoomId: string) => void) | undefined
}) {
  return (
    <select
      aria-label={`Переместить: ${student}`}
      className="rounded border border-input bg-surface px-1 py-0.5 text-caption text-foreground"
      onChange={(event) => {
        if (event.target.value) onMove?.(student, event.target.value)
      }}
      value=""
    >
      <option value="">В кабинет…</option>
      {rooms.map((room) => (
        <option key={room.id} value={room.id}>
          {room.name}
        </option>
      ))}
    </select>
  )
}

export function ClassroomPlanner({
  rooms,
  unassigned,
  conflicts = [],
  onMove,
  className,
}: ClassroomPlannerProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <p className="text-small text-muted-foreground">
        Авто-распределение расставляет учеников по вместимости и уровню; спорные случаи — ниже.
        Перемещайте вручную через «В кабинет…».
      </p>

      {conflicts.length > 0 ? (
        <Alert tone="warning">
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Конфликты распределения</AlertTitle>
            <ul className="mt-0.5 list-disc pl-4 text-small text-muted-foreground">
              {conflicts.map((conflict, index) => (
                <li key={index}>{conflict}</li>
              ))}
            </ul>
          </AlertContent>
        </Alert>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {rooms.map((room) => {
          const over = room.assigned.length > room.capacity
          return (
            <section
              aria-label={room.name}
              className="space-y-2 rounded-md border border-border bg-surface p-3"
              key={room.id}
            >
              <div className="flex items-baseline justify-between">
                <h3 className="text-label font-medium text-foreground">{room.name}</h3>
                <span
                  className={cn(
                    'font-num text-caption',
                    over ? 'text-status-danger' : 'text-muted-foreground',
                  )}
                >
                  {room.assigned.length}/{room.capacity}
                </span>
              </div>
              <ul className="space-y-1">
                {room.assigned.map((student) => (
                  <li className="flex items-center justify-between gap-2 text-small" key={student}>
                    <span className="text-foreground">{student}</span>
                    <MoveControl
                      onMove={onMove}
                      rooms={rooms.filter((other) => other.id !== room.id)}
                      student={student}
                    />
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>

      {unassigned.length > 0 ? (
        <section
          aria-label="Без кабинета"
          className="space-y-2 rounded-md border border-dashed border-border p-3"
        >
          <h3 className="text-label font-medium text-foreground">Без кабинета</h3>
          <ul className="space-y-1">
            {unassigned.map((student) => (
              <li className="flex items-center justify-between gap-2 text-small" key={student}>
                <span className="text-foreground">{student}</span>
                <MoveControl onMove={onMove} rooms={rooms} student={student} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

/* ── SOS / questions queue ──────────────────────────────────────────────── */

export interface SosItem {
  id: string
  studentName: string
  taskNumber?: string
  question: string
  at: string
  status: 'open' | 'answered'
}

export interface SosQueueProps {
  items: SosItem[]
  onOpen?: (id: string) => void
  className?: string
}

export function SosQueue({ items, onOpen, className }: SosQueueProps) {
  return (
    <ul className={cn('space-y-2', className)}>
      {items.map((item) => (
        <li
          className="flex items-start gap-3 rounded-md border border-border bg-surface p-3"
          key={item.id}
        >
          <CircleHelp
            aria-hidden="true"
            className={cn(
              'mt-0.5 size-5 shrink-0',
              item.status === 'open' ? 'text-status-info' : 'text-muted-foreground',
            )}
          />
          <div className="min-w-0 flex-1 space-y-0.5">
            <div className="flex flex-wrap items-center gap-x-2 text-small">
              <span className="font-medium text-foreground">{item.studentName}</span>
              {item.taskNumber ? (
                <span className="font-num text-muted-foreground">{item.taskNumber}</span>
              ) : null}
              <time className="text-caption text-muted-foreground">{item.at}</time>
            </div>
            <p className="line-clamp-2 text-small text-muted-foreground">{item.question}</p>
          </div>
          <Button onClick={() => onOpen?.(item.id)} size="xs" variant="outline">
            {item.status === 'open' ? 'Ответить' : 'Открыть'}
          </Button>
        </li>
      ))}
    </ul>
  )
}
