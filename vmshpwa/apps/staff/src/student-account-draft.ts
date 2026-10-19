import { z } from 'zod'

const studentAccountDraftSchema = z
  .object({ schemaVersion: z.literal(1), username: z.string().max(100) })
  .strict()

export type StudentAccountDraft = z.infer<typeof studentAccountDraftSchema>

export function studentAccountDraftKey(
  storageNamespace: string,
  staffAccountId: string,
  studentId: string,
) {
  return `${storageNamespace}:draft:student-account:${staffAccountId}:${studentId}`
}

export function readStudentAccountDraft(
  storage: Pick<Storage, 'getItem'>,
  key: string,
): StudentAccountDraft {
  try {
    const stored = storage.getItem(key)
    if (stored) return studentAccountDraftSchema.parse(JSON.parse(stored))
  } catch {
    // Corrupt or unavailable local storage falls back to an empty form.
  }
  return { schemaVersion: 1, username: '' }
}

export function writeStudentAccountDraft(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  draft: StudentAccountDraft,
) {
  try {
    storage.setItem(key, JSON.stringify(studentAccountDraftSchema.parse(draft)))
    return true
  } catch {
    return false
  }
}

export function clearStudentAccountDraft(storage: Pick<Storage, 'removeItem'>, key: string) {
  try {
    storage.removeItem(key)
  } catch {
    // The server mutation succeeded; unavailable storage must not undo it.
  }
}
