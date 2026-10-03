import { t } from '@lingui/core/macro'
import type { ScheduleField } from '@vmsh/contracts'

export const scheduleFieldLabels: Record<ScheduleField, string> = {
  get opens_at() {
    return t`Публикация условия`
  },
  get hint_scheduled_at() {
    return t`Публикация подсказки`
  },
  get submission_closes_at() {
    return t`Приём решений до`
  },
  get solution_scheduled_at() {
    return t`Публикация решения`
  },
}

export function clearScheduleDraft(storageKey: string) {
  try {
    globalThis.localStorage.removeItem(storageKey)
  } catch {
    // A successful server receipt is authoritative even if local cleanup is denied.
  }
}
