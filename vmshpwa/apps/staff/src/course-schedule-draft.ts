import type { ScheduleField } from '@vmsh/contracts'

export const scheduleFieldLabels: Record<ScheduleField, string> = {
  opens_at: 'Публикация условия',
  hint_scheduled_at: 'Публикация подсказки',
  submission_closes_at: 'Приём решений до',
  solution_scheduled_at: 'Публикация решения',
}

export function clearScheduleDraft(storageKey: string) {
  try {
    globalThis.localStorage.removeItem(storageKey)
  } catch {
    // A successful server receipt is authoritative even if local cleanup is denied.
  }
}
