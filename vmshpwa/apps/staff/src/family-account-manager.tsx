import { useState, type FormEvent } from 'react'

import {
  type AdminStudentDirectoryEntry,
  type CreateFamilyAccountRequest,
  type LinkFamilyAccountRequest,
} from '@vmsh/contracts'
import { Badge, Button, Checkbox, Input, Label } from '@vmsh/ui'

import {
  clearFamilyAccountDraft,
  familyAccountDraftKey,
  readFamilyAccountDraft,
  writeFamilyAccountDraft,
  type FamilyAccountDraft,
  type FamilyAccountDraftKind,
} from './family-account-draft'

type FamilyAccount = AdminStudentDirectoryEntry['familyAccounts'][number]

export type FamilyAccountCommand =
  | { kind: 'create'; studentId: string; input: CreateFamilyAccountRequest }
  | { kind: 'link'; studentId: string; input: LinkFamilyAccountRequest }
  | { kind: 'unlink'; studentId: string; accountId: string }

const createFallback: FamilyAccountDraft = {
  schemaVersion: 1,
  kind: 'create',
  username: '',
  displayName: '',
  relationshipLabel: 'родитель',
  isPrimary: true,
}
const linkFallback: FamilyAccountDraft = {
  schemaVersion: 1,
  kind: 'link',
  familyUsername: '',
  relationshipLabel: 'родитель',
  isPrimary: false,
}

/** Compact admin-only Family account flow from development Phase 10. */
export function FamilyAccountManager({
  accounts,
  pending,
  staffAccountId,
  storageNamespace,
  studentId,
  onChange,
}: {
  accounts: FamilyAccount[]
  pending: boolean
  staffAccountId: string
  storageNamespace: string
  studentId: string
  onChange: (command: FamilyAccountCommand) => Promise<void>
}) {
  const createKey = familyAccountDraftKey(storageNamespace, staffAccountId, studentId, 'create')
  const linkKey = familyAccountDraftKey(storageNamespace, staffAccountId, studentId, 'link')
  const [mode, setMode] = useState<FamilyAccountDraftKind | null>(null)
  const [createDraft, setCreateDraft] = useState(() =>
    readFamilyAccountDraft(globalThis.localStorage, createKey, createFallback),
  )
  const [linkDraft, setLinkDraft] = useState(() =>
    readFamilyAccountDraft(globalThis.localStorage, linkKey, linkFallback),
  )
  const [password, setPassword] = useState('')
  const [storageAvailable, setStorageAvailable] = useState(true)
  const [confirmUnlink, setConfirmUnlink] = useState<string | null>(null)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)

  function persist(next: FamilyAccountDraft) {
    setSavedMessage(null)
    if (next.kind === 'create') setCreateDraft(next)
    else setLinkDraft(next)
    const key = next.kind === 'create' ? createKey : linkKey
    setStorageAvailable(writeFamilyAccountDraft(globalThis.localStorage, key, next))
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (createDraft.kind !== 'create') return
    await onChange({
      kind: 'create',
      studentId,
      input: {
        schemaVersion: 1,
        username: createDraft.username,
        displayName: createDraft.displayName,
        password,
        relationshipLabel: createDraft.relationshipLabel,
        isPrimary: createDraft.isPrimary,
      },
    })
    clearFamilyAccountDraft(globalThis.localStorage, createKey)
    setCreateDraft(createFallback)
    setPassword('')
    setMode(null)
    setSavedMessage('Семейный аккаунт создан и привязан.')
  }

  async function submitLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (linkDraft.kind !== 'link') return
    await onChange({
      kind: 'link',
      studentId,
      input: {
        schemaVersion: 1,
        familyUsername: linkDraft.familyUsername,
        relationshipLabel: linkDraft.relationshipLabel,
        isPrimary: linkDraft.isPrimary,
      },
    })
    clearFamilyAccountDraft(globalThis.localStorage, linkKey)
    setLinkDraft(linkFallback)
    setMode(null)
    setSavedMessage('Существующий семейный аккаунт привязан.')
  }

  async function unlink(accountId: string) {
    await onChange({ kind: 'unlink', studentId, accountId })
    setConfirmUnlink(null)
    setSavedMessage('Связь со школьником удалена. Сам семейный аккаунт сохранён.')
  }

  return (
    <section aria-label="Семейные аккаунты" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-small font-medium">Семейные аккаунты</p>
          <p className="text-caption text-muted-foreground">
            Один аккаунт можно связать с несколькими детьми.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            aria-pressed={mode === 'create'}
            onClick={() => setMode(mode === 'create' ? null : 'create')}
            size="sm"
            type="button"
            variant="outline"
          >
            Создать аккаунт
          </Button>
          <Button
            aria-pressed={mode === 'link'}
            onClick={() => setMode(mode === 'link' ? null : 'link')}
            size="sm"
            type="button"
            variant="outline"
          >
            Привязать существующий
          </Button>
        </div>
      </div>

      {accounts.length === 0 ? (
        <p className="rounded-md border border-dashed border-border p-3 text-small text-muted-foreground">
          Семейных аккаунтов пока нет.
        </p>
      ) : (
        <ul className="space-y-2">
          {accounts.map((account) => (
            <li className="rounded-md border border-border px-3 py-2" key={account.accountId}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-small font-medium">{account.displayName}</p>
                  <p className="break-all text-caption text-muted-foreground">
                    {account.username} · {account.relationshipLabel ?? 'родитель'}
                    {account.isPrimary ? ' · основной контакт' : ''}
                  </p>
                </div>
                <Badge variant={account.status === 'active' ? 'success' : 'warning'}>
                  {account.status === 'active' ? 'Активен' : 'Вход отключён'}
                </Badge>
              </div>
              {confirmUnlink === account.accountId ? (
                <div className="mt-3 rounded-md bg-muted p-3 text-small" role="alert">
                  <p>Отвязать аккаунт только от этого школьника?</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      disabled={pending}
                      onClick={() => void unlink(account.accountId).catch(() => undefined)}
                      size="sm"
                      type="button"
                      variant="destructive"
                    >
                      Подтвердить отвязку
                    </Button>
                    <Button
                      disabled={pending}
                      onClick={() => setConfirmUnlink(null)}
                      size="sm"
                      type="button"
                      variant="ghost"
                    >
                      Отмена
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  className="mt-1"
                  disabled={pending}
                  onClick={() => setConfirmUnlink(account.accountId)}
                  size="sm"
                  type="button"
                  variant="ghost"
                >
                  Отвязать от школьника
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {mode === 'create' && createDraft.kind === 'create' ? (
        <form
          className="grid gap-3 rounded-md border border-border p-3 md:grid-cols-2"
          onSubmit={(event) => void submitCreate(event).catch(() => undefined)}
        >
          <p className="text-small font-medium md:col-span-2">Новый аккаунт семьи</p>
          <Label className="grid gap-1 text-small">
            Логин
            <Input
              autoComplete="off"
              disabled={pending}
              maxLength={100}
              onChange={(event) => persist({ ...createDraft, username: event.target.value })}
              required
              value={createDraft.username}
            />
          </Label>
          <Label className="grid gap-1 text-small">
            Имя аккаунта
            <Input
              disabled={pending}
              maxLength={200}
              onChange={(event) => persist({ ...createDraft, displayName: event.target.value })}
              placeholder="Например, семья Ивановых"
              required
              value={createDraft.displayName}
            />
          </Label>
          <Label className="grid gap-1 text-small">
            Первый пароль
            <Input
              autoComplete="new-password"
              disabled={pending}
              maxLength={256}
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </Label>
          <RelationshipFields draft={createDraft} disabled={pending} onChange={persist} />
          <div className="flex flex-wrap items-center gap-3 md:col-span-2">
            <Button disabled={pending} size="sm" type="submit">
              {pending ? 'Создаём…' : 'Создать и привязать'}
            </Button>
            <p className="text-caption text-muted-foreground">
              Пароль не сохраняется в браузере и после отправки не показывается снова.
            </p>
          </div>
        </form>
      ) : null}

      {mode === 'link' && linkDraft.kind === 'link' ? (
        <form
          className="grid gap-3 rounded-md border border-border p-3 md:grid-cols-2"
          onSubmit={(event) => void submitLink(event).catch(() => undefined)}
        >
          <p className="text-small font-medium md:col-span-2">Существующий аккаунт семьи</p>
          <Label className="grid gap-1 text-small">
            Семейный логин
            <Input
              autoComplete="off"
              disabled={pending}
              maxLength={100}
              onChange={(event) => persist({ ...linkDraft, familyUsername: event.target.value })}
              required
              value={linkDraft.familyUsername}
            />
          </Label>
          <RelationshipFields draft={linkDraft} disabled={pending} onChange={persist} />
          <Button className="md:col-span-2 md:w-fit" disabled={pending} size="sm" type="submit">
            {pending ? 'Привязываем…' : 'Привязать аккаунт'}
          </Button>
        </form>
      ) : null}

      {!storageAvailable ? (
        <p className="text-small text-status-error" role="alert">
          Несекретный черновик формы не сохраняется в этом браузере.
        </p>
      ) : mode !== null ? (
        <p className="text-caption text-muted-foreground" role="status">
          Логин, имя и роль сохраняются на этом устройстве до отправки. Пароль — никогда.
        </p>
      ) : null}
      {savedMessage ? (
        <p className="text-small text-status-success" role="status">
          {savedMessage}
        </p>
      ) : null}
    </section>
  )
}

function RelationshipFields({
  disabled,
  draft,
  onChange,
}: {
  disabled: boolean
  draft: FamilyAccountDraft
  onChange: (draft: FamilyAccountDraft) => void
}) {
  return (
    <>
      <Label className="grid gap-1 text-small">
        Связь со школьником
        <Input
          disabled={disabled}
          maxLength={100}
          onChange={(event) => onChange({ ...draft, relationshipLabel: event.target.value })}
          placeholder="Например, родитель"
          required
          value={draft.relationshipLabel}
        />
      </Label>
      <Label className="flex items-center gap-2 self-end pb-2 text-small">
        <Checkbox
          checked={draft.isPrimary}
          disabled={disabled}
          onCheckedChange={(checked) => onChange({ ...draft, isPrimary: checked === true })}
        />
        Основной семейный контакт
      </Label>
    </>
  )
}
