import { useState, type FormEvent } from 'react'

import type { CreateStudentAccountRequest } from '@vmsh/contracts'
import { Button, Input, Label } from '@vmsh/ui'

import {
  clearStudentAccountDraft,
  readStudentAccountDraft,
  studentAccountDraftKey,
  writeStudentAccountDraft,
} from './student-account-draft'

/** Minimal Phase-10 flow: the existing bot token stays server-side. */
export function StudentAccountCreator({
  pending,
  staffAccountId,
  storageNamespace,
  studentId,
  onCreate,
}: {
  pending: boolean
  staffAccountId: string
  storageNamespace: string
  studentId: string
  onCreate: (studentId: string, input: CreateStudentAccountRequest) => Promise<void>
}) {
  const draftKey = studentAccountDraftKey(storageNamespace, staffAccountId, studentId)
  const [draft, setDraft] = useState(() =>
    readStudentAccountDraft(globalThis.localStorage, draftKey),
  )
  const [storageAvailable, setStorageAvailable] = useState(true)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onCreate(studentId, draft)
    clearStudentAccountDraft(globalThis.localStorage, draftKey)
    setDraft({ schemaVersion: 1, username: '' })
  }

  return (
    <form
      className="grid gap-3 rounded-md border border-border p-3 sm:grid-cols-[minmax(12rem,20rem)_auto] sm:items-end"
      onSubmit={(event) => void submit(event).catch(() => undefined)}
    >
      <Label className="grid gap-1 text-small">
        Логин школьника
        <Input
          autoComplete="off"
          disabled={pending}
          maxLength={100}
          onChange={(event) => {
            const next = { schemaVersion: 1 as const, username: event.target.value }
            setDraft(next)
            setStorageAvailable(writeStudentAccountDraft(globalThis.localStorage, draftKey, next))
          }}
          required
          value={draft.username}
        />
      </Label>
      <Button disabled={pending} type="submit">
        {pending ? 'Создаём…' : 'Создать web-вход'}
      </Button>
      <p className="text-caption text-muted-foreground sm:col-span-2">
        Паролем останется текущий Telegram-токен школьника. Он не передаётся в браузер.
      </p>
      {!storageAvailable ? (
        <p className="text-small text-status-error sm:col-span-2" role="alert">
          Логин не сохраняется в этом браузере. Не закрывайте вкладку до отправки.
        </p>
      ) : draft.username ? (
        <p className="text-caption text-muted-foreground sm:col-span-2" role="status">
          Несохранённый логин хранится на этом устройстве.
        </p>
      ) : null}
    </form>
  )
}
