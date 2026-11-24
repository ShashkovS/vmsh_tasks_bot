import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
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
  get relationshipLabel() {
    return t`родитель`
  },
  isPrimary: true,
}
const linkFallback: FamilyAccountDraft = {
  schemaVersion: 1,
  kind: 'link',
  familyUsername: '',
  get relationshipLabel() {
    return t`родитель`
  },
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
    setSavedMessage(t`Аккаунт родителя создан и привязан.`)
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
    setSavedMessage(t`Существующий аккаунт родителя привязан.`)
  }

  async function unlink(accountId: string) {
    await onChange({ kind: 'unlink', studentId, accountId })
    setConfirmUnlink(null)
    setSavedMessage(t`Связь со школьником удалена. Учётная запись родителя сохранена.`)
  }

  return (
    <section aria-label={t`Аккаунты родителей`} className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-small font-medium">
            <Trans>Аккаунты родителей</Trans>
          </p>
          <p className="text-caption text-muted-foreground">
            <Trans>Один аккаунт можно связать с несколькими детьми.</Trans>
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
            <Trans>Создать аккаунт</Trans>
          </Button>
          <Button
            aria-pressed={mode === 'link'}
            onClick={() => setMode(mode === 'link' ? null : 'link')}
            size="sm"
            type="button"
            variant="outline"
          >
            <Trans>Привязать существующий</Trans>
          </Button>
        </div>
      </div>

      {accounts.length === 0 ? (
        <p className="rounded-md border border-dashed border-border p-3 text-small text-muted-foreground">
          <Trans>Аккаунтов родителей пока нет.</Trans>
        </p>
      ) : (
        <ul className="space-y-2">
          {accounts.map((account) => (
            <li className="rounded-md border border-border px-3 py-2" key={account.accountId}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-small font-medium">{account.displayName}</p>
                  <p className="break-all text-caption text-muted-foreground">
                    {account.username} · {account.relationshipLabel ?? t`родитель`}
                    {account.isPrimary ? t` · основной контакт` : ''}
                  </p>
                </div>
                <Badge variant={account.status === 'active' ? 'success' : 'warning'}>
                  {account.status === 'active' ? t`Активен` : t`Вход отключён`}
                </Badge>
              </div>
              {confirmUnlink === account.accountId ? (
                <div className="mt-3 rounded-md bg-muted p-3 text-small" role="alert">
                  <p>
                    <Trans>Отвязать аккаунт только от этого школьника?</Trans>
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      disabled={pending}
                      onClick={() => void unlink(account.accountId).catch(() => undefined)}
                      size="sm"
                      type="button"
                      variant="destructive"
                    >
                      <Trans>Подтвердить отвязку</Trans>
                    </Button>
                    <Button
                      disabled={pending}
                      onClick={() => setConfirmUnlink(null)}
                      size="sm"
                      type="button"
                      variant="ghost"
                    >
                      <Trans>Отмена</Trans>
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
                  <Trans>Отвязать от школьника</Trans>
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
          <p className="text-small font-medium md:col-span-2">
            <Trans>Новый аккаунт родителя</Trans>
          </p>
          <Label className="grid gap-1 text-small">
            <Trans>Логин</Trans>
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
            <Trans>Имя аккаунта</Trans>
            <Input
              disabled={pending}
              maxLength={200}
              onChange={(event) => persist({ ...createDraft, displayName: event.target.value })}
              placeholder={t`Например, Анна Иванова`}
              required
              value={createDraft.displayName}
            />
          </Label>
          <Label className="grid gap-1 text-small">
            <Trans>Первый пароль</Trans>
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
              {pending ? t`Создаём…` : t`Создать и привязать`}
            </Button>
            <p className="text-caption text-muted-foreground">
              <Trans>
                Пароль не сохраняется в браузере и после отправки не показывается снова.
              </Trans>
            </p>
          </div>
        </form>
      ) : null}

      {mode === 'link' && linkDraft.kind === 'link' ? (
        <form
          className="grid gap-3 rounded-md border border-border p-3 md:grid-cols-2"
          onSubmit={(event) => void submitLink(event).catch(() => undefined)}
        >
          <p className="text-small font-medium md:col-span-2">
            <Trans>Существующий аккаунт родителя</Trans>
          </p>
          <Label className="grid gap-1 text-small">
            <Trans>Логин родителя</Trans>
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
            {pending ? t`Привязываем…` : t`Привязать аккаунт`}
          </Button>
        </form>
      ) : null}

      {!storageAvailable ? (
        <p className="text-small text-status-error" role="alert">
          <Trans>Несекретный черновик формы не сохраняется в этом браузере.</Trans>
        </p>
      ) : mode !== null ? (
        <p className="text-caption text-muted-foreground" role="status">
          <Trans>
            Логин, имя и роль сохраняются на этом устройстве до отправки. Пароль — никогда.
          </Trans>
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
        <Trans>Связь со школьником</Trans>
        <Input
          disabled={disabled}
          maxLength={100}
          onChange={(event) => onChange({ ...draft, relationshipLabel: event.target.value })}
          placeholder={t`Например, родитель`}
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
        <Trans>Основной родительский контакт</Trans>
      </Label>
    </>
  )
}
