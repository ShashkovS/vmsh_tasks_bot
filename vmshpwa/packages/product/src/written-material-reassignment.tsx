import { AlertTriangle, FileText, ImageIcon, MoveRight, RotateCcw } from 'lucide-react'
import { useId, useMemo, useState } from 'react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Checkbox,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  cn,
} from '@vmsh/ui'

export type WrittenMaterialKind = 'entry_text' | 'attachment'

export interface WrittenMaterialSelection {
  entryId: string
  itemKind: WrittenMaterialKind
  attachmentId: string | null
}

export interface WrittenMaterialChoice extends WrittenMaterialSelection {
  id: string
  label: string
  text?: string | undefined
  previewUrl?: string | undefined
  locked?: boolean | undefined
}

export interface WrittenMaterialTarget {
  problemId: string
  taskLabel: string
  contextLabel: string
}

export interface WrittenMaterialReassignmentPreviewView {
  targetProblemId: string
  postReview: boolean
  selectedCount: number
}

export interface WrittenMaterialReassignmentProps {
  studentName: string
  sourceLabel: string
  materials: WrittenMaterialChoice[]
  targets: WrittenMaterialTarget[]
  preview?: WrittenMaterialReassignmentPreviewView | null | undefined
  initialSelectedIds?: string[] | undefined
  initialTargetProblemId?: string | undefined
  busy?: boolean | undefined
  errorMessage?: string | undefined
  successMessage?: string | undefined
  onPreview: (targetProblemId: string, items: WrittenMaterialSelection[]) => void
  onConfirm: (
    targetProblemId: string,
    items: WrittenMaterialSelection[],
    reason: string | null,
  ) => void
  onResetPreview?: (() => void) | undefined
  className?: string | undefined
}

function selectionOf(material: WrittenMaterialChoice): WrittenMaterialSelection {
  return {
    entryId: material.entryId,
    itemKind: material.itemKind,
    attachmentId: material.attachmentId,
  }
}

function materialCountLabel(count: number) {
  const remainder100 = count % 100
  const remainder10 = count % 10

  if (remainder100 >= 11 && remainder100 <= 14) {
    return `${count} материалов будут показаны`
  }
  if (remainder10 === 1) {
    return `${count} материал будет показан`
  }
  if (remainder10 >= 2 && remainder10 <= 4) {
    return `${count} материала будут показаны`
  }
  return `${count} материалов будут показаны`
}

export function WrittenMaterialReassignment({
  studentName,
  sourceLabel,
  materials,
  targets,
  preview,
  initialSelectedIds = [],
  initialTargetProblemId,
  busy,
  errorMessage,
  successMessage,
  onPreview,
  onConfirm,
  onResetPreview,
  className,
}: WrittenMaterialReassignmentProps) {
  const targetId = useId()
  const reasonId = useId()
  const [selected, setSelected] = useState(() => new Set(initialSelectedIds))
  const [targetProblemId, setTargetProblemId] = useState(initialTargetProblemId ?? '')
  const [reason, setReason] = useState('')
  const selectedItems = useMemo(
    () => materials.filter((material) => selected.has(material.id)).map(selectionOf),
    [materials, selected],
  )
  const target = targets.find((item) => item.problemId === targetProblemId)
  const previewActive = preview !== null && preview !== undefined

  const toggle = (id: string, checked: boolean) => {
    setSelected((current) => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  return (
    <section
      aria-label="Исправить привязку письменной работы"
      className={cn('w-full space-y-4 rounded-lg border border-border bg-surface p-4', className)}
      data-density="staff"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-title-sm font-semibold text-foreground">
            Перенести материал в другую задачу
          </h3>
          <p className="text-small text-muted-foreground">
            {studentName} · сейчас в {sourceLabel}
          </p>
        </div>
        <Badge variant="neutral">Исправление привязки</Badge>
      </header>

      <fieldset className="space-y-2" disabled={busy || previewActive}>
        <legend className="text-label font-medium text-foreground">Что переносим</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {materials.map((material) => (
            <label
              className="flex min-w-0 cursor-pointer items-start gap-2 rounded-md border border-border bg-surface-raised p-2 has-checked:border-primary has-checked:bg-accent/50"
              key={material.id}
            >
              <Checkbox
                aria-label={`Выбрать: ${material.label}`}
                checked={selected.has(material.id)}
                onCheckedChange={(checked) => toggle(material.id, checked === true)}
              />
              {material.itemKind === 'attachment' ? (
                material.previewUrl ? (
                  <img
                    alt=""
                    className="size-14 shrink-0 rounded-sm border border-border object-cover"
                    src={material.previewUrl}
                  />
                ) : (
                  <span className="grid size-14 shrink-0 place-items-center rounded-sm bg-surface-sunken text-muted-foreground">
                    <ImageIcon aria-hidden="true" className="size-5" />
                  </span>
                )
              ) : (
                <FileText
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                />
              )}
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1 text-small font-medium text-foreground">
                  {material.label}
                  {material.locked ? <Badge variant="warning">После проверки</Badge> : null}
                </span>
                {material.text ? (
                  <span className="mt-0.5 line-clamp-3 block text-caption text-muted-foreground">
                    {material.text}
                  </span>
                ) : null}
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,0.6fr)]">
        <div className="min-w-0 space-y-1">
          <Label htmlFor={targetId}>Целевая задача</Label>
          <Select
            disabled={busy || previewActive}
            onValueChange={(value) => setTargetProblemId(value ?? '')}
            value={targetProblemId || null}
          >
            <SelectTrigger className="w-full min-w-0 overflow-hidden" id={targetId} size="sm">
              <SelectValue className="min-w-0 overflow-hidden">
                <span className="block min-w-0 truncate">
                  {target ? `${target.taskLabel} · ${target.contextLabel}` : 'Выберите задачу'}
                </span>
              </SelectValue>
            </SelectTrigger>
            <SelectContent align="start">
              {targets.map((item) => (
                <SelectItem key={item.problemId} value={item.problemId}>
                  <span className="min-w-0">
                    <span className="block truncate">{item.taskLabel}</span>
                    <span className="block truncate text-caption text-muted-foreground">
                      {item.contextLabel}
                    </span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-0 space-y-1">
          <Label htmlFor={reasonId}>Причина для журнала (необязательно)</Label>
          <Input
            disabled={busy || previewActive}
            id={reasonId}
            maxLength={2000}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Например, выбран соседний номер"
            value={reason}
          />
        </div>
      </div>

      {previewActive ? (
        <Alert tone={preview.postReview ? 'warning' : 'neutral'}>
          <AlertTriangle aria-hidden="true" />
          <AlertContent>
            <AlertTitle>{materialCountLabel(preview.selectedCount)} в другой задаче</AlertTitle>
            <AlertDescription>
              Исходные сообщения, фотографии и их байты останутся на месте. Вердикт не переносится.
              {preview.postReview
                ? ' Проверка уже началась: зафиксированное evidence и прежний вердикт останутся неизменными.'
                : ''}
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {errorMessage ? (
        <p className="text-small text-status-danger" role="alert">
          {errorMessage}
        </p>
      ) : null}
      {successMessage ? (
        <p className="text-small text-status-success" role="status">
          {successMessage}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {previewActive ? (
          <>
            <Button
              disabled={busy}
              onClick={() => onConfirm(targetProblemId, selectedItems, reason.trim() || null)}
              size="sm"
            >
              <MoveRight aria-hidden="true" />
              {busy ? 'Переносим…' : 'Подтвердить перенос'}
            </Button>
            <Button disabled={busy} onClick={onResetPreview} size="sm" variant="outline">
              <RotateCcw aria-hidden="true" />
              Изменить выбор
            </Button>
          </>
        ) : (
          <Button
            disabled={busy || selectedItems.length === 0 || !targetProblemId}
            onClick={() => onPreview(targetProblemId, selectedItems)}
            size="sm"
            variant="outline"
          >
            Проверить перенос
          </Button>
        )}
        <span className="text-caption text-muted-foreground">
          Выбрано: {selectedItems.length} из {materials.length}
        </span>
      </div>
    </section>
  )
}
