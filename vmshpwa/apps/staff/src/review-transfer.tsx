import { useState } from 'react'
import {
  ApiResponseError,
  type ReviewTransferPreview,
  type ReviewTransferRequest,
  type ReviewTransferResponse,
} from '@vmsh/contracts'
import { type ReviewQueueClient } from '@vmsh/app-shell'
import { Button, Label } from '@vmsh/ui'
import { describeReviewError } from './review-errors'

/** Whole submitted entry, never the whole dialogue; docs/serial-review-feed.md. */
export function ReviewTransfer({
  client,
  queueId,
  entryId,
  claimToken,
  disabled,
  onBusy,
  onDone,
}: {
  client: ReviewQueueClient
  queueId: string
  entryId: string
  claimToken: string
  disabled: boolean
  onBusy: (busy: boolean) => void
  onDone: (result: ReviewTransferResponse) => Promise<void>
}) {
  const [preview, setPreview] = useState<ReviewTransferPreview | null>(null)
  const [mode, setMode] = useState<'move' | 'clone'>('move')
  const [target, setTarget] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [busy, setBusy] = useState(false)
  const [request, setRequest] = useState<ReviewTransferRequest | null>(null)
  const open = async (next: 'move' | 'clone') => {
    if (busy || disabled) return
    setConflict(false)
    setMode(next)
    setError(null)
    setBusy(true)
    onBusy(true)
    try {
      setPreview(await client.transferPreview(queueId, entryId, claimToken))
      setTarget('')
      setRequest(null)
    } catch (e) {
      setError(describeReviewError(e))
      setConflict(e instanceof ApiResponseError && e.status === 409)
    } finally {
      setBusy(false)
      onBusy(false)
    }
  }
  const send = async () => {
    if (!preview || !target || busy) return
    const selected = preview.targets.find((t) => t.problemId === target)
    if (!selected) return
    const payload: ReviewTransferRequest = request ?? {
      schemaVersion: 1,
      entryId,
      claimToken,
      targetProblemId: target,
      sourceVersion: preview.sourceVersion,
      entryVersion: preview.entryVersion,
      targetVersion: selected.threadVersion,
      targetThreadId: selected.threadId,
      mode,
      idempotencyKey: crypto.randomUUID(),
    }
    setRequest(payload)
    setBusy(true)
    onBusy(true)
    setError(null)
    try {
      const result = await client.transfer(queueId, payload)
      setPreview(null)
      await onDone(result)
    } catch (e) {
      setError(describeReviewError(e))
      setConflict(e instanceof ApiResponseError && e.status === 409)
    } finally {
      setBusy(false)
      onBusy(false)
    }
  }
  return (
    <div className="my-2 space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={disabled || busy}
          onClick={() => void open('move')}
        >
          Перенести в другую задачу
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={disabled || busy}
          onClick={() => void open('clone')}
        >
          Клонировать в другую задачу
        </Button>
      </div>
      {error && <p role="alert">{error}</p>}
      {conflict && (
        <Button
          size="sm"
          variant="outline"
          disabled={busy || disabled}
          onClick={() => void open(mode)}
        >
          Обновить предпросмотр
        </Button>
      )}
      {preview && (
        <section
          aria-label="Подтверждение переноса посылки"
          className="space-y-3 rounded-lg border border-border p-3"
        >
          <p>
            {preview.studentName} · {preview.sourceLabel} · фотографий: {preview.photoCount}
          </p>
          <Label>
            Целевая задача
            <select
              className="block w-full rounded border border-border bg-surface p-2"
              disabled={busy || request !== null}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            >
              <option value="">Выберите задачу</option>
              {preview.targets.map((t) => (
                <option key={t.problemId} value={t.problemId}>
                  {t.label}
                </option>
              ))}
            </select>
          </Label>
          {!preview.targets.length && (
            <p>Нет подходящих письменных или устных задач этого занятия и уровня.</p>
          )}
          <p>
            {mode === 'move'
              ? 'Вся посылка будет перенесена в целевую очередь. Вы перейдёте к следующей работе.'
              : 'Копия всей посылки попадёт в целевую очередь. Исходная останется здесь.'}{' '}
            Оценка и учительские пометки не копируются.
          </p>
          <div className="flex gap-2">
            <Button disabled={busy || !target} onClick={() => void send()}>
              {busy
                ? 'Сохраняем…'
                : request
                  ? 'Повторить запрос'
                  : mode === 'move'
                    ? 'Перенести посылку'
                    : 'Клонировать посылку'}
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => setPreview(null)}>
              Закрыть
            </Button>
          </div>
        </section>
      )}
    </div>
  )
}
