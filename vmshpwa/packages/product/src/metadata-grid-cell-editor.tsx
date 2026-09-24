import { useEffect, useRef, useState } from 'react'

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Textarea,
} from '@vmsh/ui'

import type { MetadataColumn } from './metadata-grid-types'

export function MetadataGridCellEditor({
  column,
  displayNumber,
  initialValue,
  onApply,
  onClose,
}: {
  column: MetadataColumn
  displayNumber: string
  initialValue: string
  onApply: (value: string) => void
  onClose: () => void
}) {
  const [value, setValue] = useState(initialValue)
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(null)

  useEffect(() => {
    const control = inputRef.current
    control?.focus()
    if (control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement)
      control.select()
  }, [])

  const apply = () => onApply(value)
  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault()
      apply()
      return
    }
    if (column.editor !== 'textarea' && event.key === 'Enter') {
      event.preventDefault()
      apply()
    }
  }

  return (
    <Dialog
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      open
    >
      <DialogContent showCloseButton={false} className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{column.header}</DialogTitle>
          <DialogDescription>Задача {displayNumber || 'без номера'}</DialogDescription>
        </DialogHeader>
        {column.editor === 'select' ? (
          <select
            aria-label={column.header}
            className="min-h-(--touch-target) w-full rounded-md border border-input bg-surface px-3 py-1 text-small text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
            onChange={(event) => setValue(event.target.value)}
            ref={inputRef as React.RefObject<HTMLSelectElement>}
            value={value}
          >
            <option value="">—</option>
            {value && !column.options?.some((option) => option.value === value) ? (
              <option value={value}>{value}</option>
            ) : null}
            {(column.options ?? []).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        ) : column.editor === 'textarea' ? (
          <Textarea
            aria-label={column.header}
            className="min-h-52"
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={onKeyDown}
            ref={inputRef as React.RefObject<HTMLTextAreaElement>}
            value={value}
          />
        ) : (
          <Input
            aria-label={column.header}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={onKeyDown}
            ref={inputRef as React.RefObject<HTMLInputElement>}
            value={value}
          />
        )}
        <DialogFooter>
          <Button onClick={onClose} variant="outline">
            Отмена
          </Button>
          <Button onClick={apply}>Применить</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
