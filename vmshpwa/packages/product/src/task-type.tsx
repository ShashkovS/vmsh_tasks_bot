import { t } from '@lingui/core/macro'
import { FileText, Mic, PenLine } from 'lucide-react'

import { cn } from '@vmsh/ui'

import type { TaskType } from './types'

/*
 * Task type. Four technical types collapse to three for the student
 * (WRITTEN_BEFORE_ORALLY shows as oral). The icon has an accessible name; the
 * submission rule is exposed for a tap/hover explanation at the use site.
 */
const config: Record<TaskType, { Icon: typeof FileText; name: string; rule: string }> = {
  test: {
    Icon: FileText,
    get name() {
 return t`Тестовая задача`
},
    get rule() {
 return t`Ответ вводится прямо в интерфейсе и проверяется автоматически.`
},
  },
  written: {
    Icon: PenLine,
    get name() {
 return t`Письменная задача`
},
    get rule() {
 return t`Решение отправляется текстом и фотографиями, проверяет преподаватель.`
},
  },
  oral: {
    Icon: Mic,
    get name() {
 return t`Устная задача`
},
    get rule() {
 return t`Сдаётся устно в конференции; в окне приёма можно отправить и письменно.`
},
  },
}

export function taskTypeName(type: TaskType): string {
  return config[type].name
}

export function taskTypeRule(type: TaskType): string {
  return config[type].rule
}

export interface TaskTypeIconProps {
  type: TaskType
  className?: string
}

export function TaskTypeIcon({ type, className }: TaskTypeIconProps) {
  const { Icon, name } = config[type]
  return (
    <Icon
      aria-label={name}
      className={cn('size-4 shrink-0 text-muted-foreground', className)}
      strokeWidth={1.75}
    />
  )
}
