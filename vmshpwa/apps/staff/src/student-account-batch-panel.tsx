import { useMemo, useState } from 'react'

import type { AdminStudentDirectoryEntry } from '@vmsh/contracts'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
} from '@vmsh/ui'

import {
  readStudentAccountBatchDraft,
  studentAccountBatchDraftKey,
  writeStudentAccountBatchDraft,
} from './student-account-batch-draft'
import { filterStudents } from './student-directory-search'

export interface StudentAccountBatchCommand {
  studentId: string
  username: string
}

export interface StudentAccountBatchResult {
  createdStudentIds: string[]
  failures: Array<{ studentId: string; message: string }>
}

function fullName(student: AdminStudentDirectoryEntry) {
  return [student.surname, student.name, student.middleName].filter(Boolean).join(' ')
}

/** Daily Phase-10 helper; initial migration remains the guarded auth-import CLI. */
export function StudentAccountBatchPanel({
  pending,
  staffAccountId,
  storageNamespace,
  students,
  onCreate,
}: {
  pending: boolean
  staffAccountId: string
  storageNamespace: string
  students: AdminStudentDirectoryEntry[]
  onCreate: (commands: StudentAccountBatchCommand[]) => Promise<StudentAccountBatchResult>
}) {
  const draftKey = studentAccountBatchDraftKey(storageNamespace, staffAccountId)
  const [selectedIds, setSelectedIds] = useState(
    () => new Set(readStudentAccountBatchDraft(globalThis.localStorage, draftKey).studentIds),
  )
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const [result, setResult] = useState<StudentAccountBatchResult | null>(null)
  const candidates = useMemo(
    () =>
      students.filter(
        (student) => student.webAccount === null && student.usernameSuggestion?.state === 'ready',
      ),
    [students],
  )
  const candidateIds = useMemo(
    () => new Set(candidates.map((student) => student.studentId)),
    [candidates],
  )
  const studentNames = useMemo(
    () => new Map(students.map((student) => [student.studentId, fullName(student)])),
    [students],
  )
  const selectedCandidates = candidates.filter((student) => selectedIds.has(student.studentId))
  const matches = filterStudents(candidates, query)
  const listedMatches = matches.slice(0, 100)
  const withoutAccount = students.filter((student) => student.webAccount === null).length
  const needsManualLogin = withoutAccount - candidates.length

  function saveSelection(next: Set<string>) {
    setSelectedIds(next)
    setStorageAvailable(writeStudentAccountBatchDraft(globalThis.localStorage, draftKey, next))
  }

  function selectMatches() {
    const next = new Set([...selectedIds].filter((studentId) => candidateIds.has(studentId)))
    for (const student of matches) next.add(student.studentId)
    saveSelection(next)
  }

  async function createSelected() {
    const commands = selectedCandidates.map((student) => {
      const suggestion = student.usernameSuggestion
      if (suggestion?.state !== 'ready') throw new Error('Batch candidate lost its login')
      return { studentId: student.studentId, username: suggestion.username }
    })
    const nextResult = await onCreate(commands)
    setResult(nextResult)
    const created = new Set(nextResult.createdStudentIds)
    saveSelection(new Set([...selectedIds].filter((studentId) => !created.has(studentId))))
  }

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Создать web-входы</CardTitle>
          <div className="flex flex-wrap gap-1">
            <Badge variant="neutral">Без входа: {withoutAccount}</Badge>
            <Badge variant="success">Готовы: {candidates.length}</Badge>
            {needsManualLogin > 0 ? (
              <Badge variant="warning">Проверить вручную: {needsManualLogin}</Badge>
            ) : null}
          </div>
        </div>
        <p className="text-small text-muted-foreground">
          Для выбранных школьников будет создан вход с предложенным логином. Паролем останется их
          текущий Telegram-токен; он не передаётся в браузер.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            disabled={pending || candidates.length === 0}
            onClick={() => setExpanded((value) => !value)}
            type="button"
            variant="outline"
          >
            {expanded ? 'Скрыть выбор' : 'Выбрать школьников'}
          </Button>
          <Button
            disabled={pending || selectedCandidates.length === 0}
            onClick={() => void createSelected().catch(() => undefined)}
            type="button"
          >
            {pending
              ? 'Создаём…'
              : `Создать аккаунты${selectedCandidates.length ? ` · ${selectedCandidates.length}` : ''}`}
          </Button>
          {selectedCandidates.length > 0 ? (
            <Button
              disabled={pending}
              onClick={() => saveSelection(new Set())}
              type="button"
              variant="ghost"
            >
              Снять выбор
            </Button>
          ) : null}
        </div>

        {expanded ? (
          <div className="space-y-3 rounded-md border border-border p-3">
            <div className="flex flex-wrap items-end gap-2">
              <Label className="grid min-w-[16rem] flex-1 gap-1 text-small">
                Поиск среди готовых
                <Input
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Фамилия, имя или часть с опечаткой"
                  type="search"
                  value={query}
                />
              </Label>
              <Button
                disabled={pending || matches.length === 0}
                onClick={selectMatches}
                type="button"
                variant="outline"
              >
                Выбрать найденных · {matches.length}
              </Button>
            </div>
            <div className="max-h-72 overflow-y-auto" role="group" aria-label="Готовые аккаунты">
              {listedMatches.map((student) => (
                <Label
                  className="grid min-h-9 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-b border-border px-1 text-small last:border-b-0"
                  key={student.studentId}
                >
                  <Checkbox
                    checked={selectedIds.has(student.studentId)}
                    disabled={pending}
                    onCheckedChange={(checked) => {
                      const next = new Set(selectedIds)
                      if (checked === true) next.add(student.studentId)
                      else next.delete(student.studentId)
                      saveSelection(next)
                    }}
                  />
                  <span className="truncate">{fullName(student)}</span>
                  <code className="text-caption">{student.usernameSuggestion!.username}</code>
                </Label>
              ))}
            </div>
            {matches.length > listedMatches.length ? (
              <p className="text-caption text-muted-foreground">
                Показаны первые 100 из {matches.length}. Уточните поиск или выберите всех найденных.
              </p>
            ) : null}
            <p className="text-caption text-muted-foreground" role="status">
              Выбрано: {selectedCandidates.length}. Выбор хранится на этом устройстве до создания
              аккаунтов или явной отмены.
            </p>
          </div>
        ) : null}

        {!storageAvailable ? (
          <p className="text-small text-status-error" role="alert">
            Выбор не сохраняется в этом браузере. Не закрывайте вкладку до создания аккаунтов.
          </p>
        ) : null}
        {result ? (
          <div className="text-small" role={result.failures.length ? 'alert' : 'status'}>
            Создано: {result.createdStudentIds.length}. Ошибок: {result.failures.length}.
            {result.failures.length ? (
              <ul className="mt-1 list-disc pl-5">
                {result.failures.slice(0, 10).map((failure) => (
                  <li key={failure.studentId}>
                    {studentNames.get(failure.studentId) ?? failure.studentId}: {failure.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
