import { z } from 'zod'

const studentAccountBatchDraftSchema = z
  .object({
    schemaVersion: z.literal(1),
    studentIds: z.array(z.string().trim().min(1).max(128)).max(2_000),
  })
  .strict()

export interface StudentAccountBatchDraft {
  schemaVersion: 1
  studentIds: string[]
}

export function studentAccountBatchDraftKey(storageNamespace: string, staffAccountId: string) {
  return `${storageNamespace}:draft:student-account-batch:${staffAccountId}`
}

export function readStudentAccountBatchDraft(
  storage: Pick<Storage, 'getItem'>,
  key: string,
): StudentAccountBatchDraft {
  try {
    const stored = storage.getItem(key)
    if (stored) {
      const draft = studentAccountBatchDraftSchema.parse(JSON.parse(stored))
      return { ...draft, studentIds: [...new Set(draft.studentIds)] }
    }
  } catch {
    // Corrupt or unavailable local storage falls back to no selection.
  }
  return { schemaVersion: 1, studentIds: [] }
}

export function writeStudentAccountBatchDraft(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  studentIds: Iterable<string>,
) {
  try {
    const draft = studentAccountBatchDraftSchema.parse({
      schemaVersion: 1,
      studentIds: [...new Set(studentIds)],
    })
    storage.setItem(key, JSON.stringify(draft))
    return true
  } catch {
    return false
  }
}
