import { useEffect, useMemo, useState } from 'react'
import { CloudOff, TriangleAlert } from 'lucide-react'

import {
  createTestSubmissionClient,
  submissionFailureMessage,
  reportHandledError,
  useAuthentication,
  useTestAnswerInputQuery,
  useTestAttemptHistoryQuery,
} from '@vmsh/app-shell'
import { type SubmitTestAnswerResponse } from '@vmsh/contracts'
import {
  createTestAnswerDraftStore,
  createTestAnswerOutbox,
  useOfflineDatabase,
  type TestAnswerDraft,
  type TestAnswerDraftDescriptor,
  type TestAnswerOutboxItem,
} from '@vmsh/offline'
import {
  ChatComposer,
  TaskChat,
  TestAnswer,
  validateAnswerFormat,
  type ChatMessageView,
} from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  Skeleton,
} from '@vmsh/ui'

import { createOfflineStudentTestAnswerInputClient } from './offline-student-data'
import { announceSafePwaUpdateMoment } from './pwa-update-events'
import { chatDate, chatTime } from './student-written-chat'
import { testAnswerSpec, testAttemptReply, testAttemptVerdict } from './student-test-answer-view'

/**
 * Production Phase-4 test editor. It composes the safe input endpoint,
 * account/revision local draft and durable outbox described in
 * `dev/development-plan/08-phase-4-test-submissions.md`.
 */

type SendState = 'ready' | 'sending' | 'queued' | 'conflict' | 'failed' | 'synced'

/** Recent turns stay in view; older ones load on request. */
const VISIBLE_TURNS = 6

function sendErrorMessage(error: unknown): string {
  reportHandledError(error, 'test.submit')
  return submissionFailureMessage(error)
}

function relevantQueueItem(
  items: TestAnswerOutboxItem[],
  problemId: string,
  descriptor: TestAnswerDraftDescriptor,
): TestAnswerOutboxItem | null {
  return (
    items
      .filter(
        (item) =>
          item.payload.problemId === problemId &&
          item.payload.request.problemRevision.conditionRevisionId ===
            descriptor.conditionRevisionId &&
          item.payload.request.problemRevision.configVersion === descriptor.configVersion,
      )
      .at(-1) ?? null
  )
}

function queueState(item: TestAnswerOutboxItem | null): SendState {
  if (!item) return 'ready'
  if (item.status === 'queued' || item.status === 'retrying' || item.status === 'sending') {
    return item.status === 'sending' ? 'sending' : 'queued'
  }
  return item.status
}

export function StudentTestAnswer({
  problemId,
  closed = false,
}: {
  problemId: string
  closed?: boolean
}) {
  const authentication = useAuthentication()
  const principal =
    authentication.state.status === 'authenticated' ||
    authentication.state.status === 'offline-unverified'
      ? authentication.state.principal
      : null
  if (!principal || principal.audience !== 'student') {
    throw new Error('Student test answer requires an authenticated Student principal')
  }
  const ownerId = principal.accountId
  const database = useOfflineDatabase()
  const online = useMemo(
    () =>
      createTestSubmissionClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const inputClient = useMemo(
    () =>
      createOfflineStudentTestAnswerInputClient(
        { input: (id, options) => online.input(id, options) },
        database,
        ownerId,
      ),
    [database, online, ownerId],
  )
  const principalScope = useMemo(
    () => ({ audience: 'student' as const, accountId: ownerId }),
    [ownerId],
  )
  const inputQuery = useTestAnswerInputQuery(inputClient, principalScope, problemId)
  const historyQuery = useTestAttemptHistoryQuery(online, principalScope, problemId)
  const outbox = useMemo(() => createTestAnswerOutbox(database, ownerId), [database, ownerId])
  const draftStore = useMemo(() => {
    try {
      return {
        value: createTestAnswerDraftStore(
          { audience: 'student', instance: authentication.client.runtime.instance },
          window.localStorage,
        ),
        error: null,
      }
    } catch (error) {
      return { value: null, error }
    }
  }, [authentication.client.runtime.instance])

  const input = inputQuery.data ?? null
  const identity = input
    ? `${ownerId}:${problemId}:${input.problemRevision.conditionRevisionId}:${input.problemRevision.configVersion}`
    : null
  const descriptor = useMemo<TestAnswerDraftDescriptor | null>(
    () =>
      input
        ? {
            ownerId,
            problemId,
            conditionRevisionId: input.problemRevision.conditionRevisionId,
            configVersion: input.problemRevision.configVersion,
          }
        : null,
    [input, ownerId, problemId],
  )
  const spec = useMemo(() => (input ? testAnswerSpec(input) : null), [input])
  const [hydratedIdentity, setHydratedIdentity] = useState<string | null>(null)
  const [answer, setAnswer] = useState('')
  const [incompatibleDraft, setIncompatibleDraft] = useState<TestAnswerDraft | null>(null)
  const [storageError, setStorageError] = useState<unknown>(draftStore.error)
  useEffect(() => {
    if (storageError)
      reportHandledError(storageError, 'test.storage', { accountId: ownerId, problemId })
  }, [storageError, ownerId, problemId])
  const [sendState, setSendState] = useState<SendState>('ready')
  const [pendingItem, setPendingItem] = useState<TestAnswerOutboxItem | null>(null)
  const [receipt, setReceipt] = useState<SubmitTestAnswerResponse | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [showFormatError, setShowFormatError] = useState(false)
  const [editorEpoch, setEditorEpoch] = useState(0)
  const [showEveryTurn, setShowEveryTurn] = useState(false)

  useEffect(() => {
    if (!identity || !descriptor || !draftStore.value) return
    let active = true
    queueMicrotask(() => {
      if (!active) return
      try {
        const local = draftStore.value?.load(descriptor)
        setAnswer(local?.compatible?.displayAnswer ?? '')
        setIncompatibleDraft(local?.incompatible[0] ?? null)
        setHydratedIdentity(identity)
        setStorageError(null)
      } catch (error) {
        setHydratedIdentity(identity)
        setStorageError(error)
      }

      void outbox.list().then(
        async (items) => {
          if (!active) return
          const item = relevantQueueItem(items, problemId, descriptor)
          if (!item) return
          setPendingItem(item)
          setSendState(queueState(item))
          setSendError(item.lastError ? submissionFailureMessage(undefined, item.lastError) : null)
          if (item.status !== 'synced' || !item.result) return
          setReceipt(item.result)
          try {
            draftStore.value?.clear(descriptor)
            await outbox.acknowledge(item.id)
            if (active) {
              setAnswer('')
              setPendingItem(null)
              setEditorEpoch((value) => value + 1)
            }
          } catch (error) {
            if (active) setStorageError(error)
          }
        },
        (error) => {
          if (active) setStorageError(error)
        },
      )
    })
    return () => {
      active = false
    }
  }, [descriptor, draftStore.value, identity, outbox, problemId])

  if (
    inputQuery.isPending ||
    (draftStore.value !== null && identity !== null && hydratedIdentity !== identity)
  ) {
    return (
      <Card aria-label="Загрузка поля ответа" className="mt-5">
        <CardContent className="space-y-3 pt-5">
          <Skeleton className="h-5 w-28" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-9 w-32" />
        </CardContent>
      </Card>
    )
  }

  if (inputQuery.error || !input || !descriptor || !spec || !draftStore.value) {
    return (
      <Alert className="mt-5" role="alert" tone="danger">
        <TriangleAlert aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Не удалось подготовить поле ответа</AlertTitle>
          <AlertDescription>
            {draftStore.error
              ? 'Браузер не разрешил надёжно сохранять введённый ответ.'
              : 'Повторите загрузку. Уже сохранённые ответы не удалены.'}
          </AlertDescription>
          {!draftStore.error ? (
            <Button className="mt-2" onClick={() => void inputQuery.refetch()} size="sm">
              Повторить
            </Button>
          ) : null}
        </AlertContent>
      </Alert>
    )
  }

  const saveAnswer = (value: string) => {
    setAnswer(value)
    setShowFormatError(false)
    try {
      draftStore.value.save(descriptor, value)
      setStorageError(null)
    } catch (error) {
      setStorageError(error)
    }
  }

  const restoreOldDraft = () => {
    if (!incompatibleDraft) return
    saveAnswer(incompatibleDraft.displayAnswer)
    setIncompatibleDraft(null)
    setEditorEpoch((value) => value + 1)
  }

  const deliver = async () => {
    if (!pendingItem) return
    setSendState('sending')
    setSendError(null)
    let result = await outbox.deliverNext(online, pendingItem.id)
    if (result.state === 'idle') {
      const stored = (await outbox.list()).find((item) => item.id === pendingItem.id)
      if (stored?.status === 'synced' && stored.result) {
        result = { state: 'synced', item: stored, receipt: stored.result }
      } else {
        setPendingItem(stored ?? null)
        setSendState(queueState(stored ?? null))
        setSendError(
          stored?.lastError ? submissionFailureMessage(undefined, stored.lastError) : null,
        )
        return
      }
    }
    if (result.item.id !== pendingItem?.id) {
      setSendState('queued')
      return
    }
    setPendingItem(result.item)
    setSendState(result.state === 'retrying' ? 'queued' : result.state)
    if (result.state !== 'synced') {
      reportHandledError(result.error, 'test.submit', {
        accountId: result.item.ownerId,
        problemId,
        outboxId: result.item.id,
        attempts: result.item.attempts,
      })
      setSendError(sendErrorMessage(result.error))
      if (result.state === 'conflict') void inputQuery.refetch()
      return
    }

    setReceipt(result.receipt)
    try {
      draftStore.value.clear(descriptor)
      await outbox.acknowledge(result.item.id)
      setPendingItem(null)
      setAnswer('')
      setEditorEpoch((value) => value + 1)
      await historyQuery.refetch()
      announceSafePwaUpdateMoment()
    } catch (error) {
      setStorageError(error)
    }
  }

  const submit = async () => {
    setShowFormatError(true)
    if (!answer.trim() || !validateAnswerFormat(spec, answer)) return
    if (pendingItem && ['queued', 'retrying', 'sending'].includes(pendingItem.status)) {
      await deliver()
      return
    }
    try {
      const queued = await outbox.enqueue({
        problemId,
        problemRevision: input.problemRevision,
        displayAnswer: answer,
      })
      setPendingItem(queued)
      // Do not claim that an answer is safely waiting for retry while its
      // first network delivery still owns the outbox sending lease. The
      // queued state is shown only after deliverNext persisted a retryable
      // failure, so a reload cannot strand a just-created answer as sending.
      setSendState('sending')
      const result = await outbox.deliverNext(online, queued.id)
      if (result.state === 'idle' || result.item.id !== queued.id) {
        setSendState('queued')
        return
      }
      setPendingItem(result.item)
      setSendState(result.state === 'retrying' ? 'queued' : result.state)
      if (result.state !== 'synced') {
        reportHandledError(result.error, 'test.submit', {
          accountId: result.item.ownerId,
          problemId,
          outboxId: result.item.id,
          attempts: result.item.attempts,
        })
        setSendError(sendErrorMessage(result.error))
        if (result.state === 'conflict') void inputQuery.refetch()
        return
      }
      setReceipt(result.receipt)
      draftStore.value.clear(descriptor)
      await outbox.acknowledge(result.item.id)
      setPendingItem(null)
      setAnswer('')
      setEditorEpoch((value) => value + 1)
      await historyQuery.refetch()
      announceSafePwaUpdateMoment()
    } catch (error) {
      setSendState('failed')
      setSendError(sendErrorMessage(error))
    }
  }

  const queuedSend =
    pendingItem !== null && ['queued', 'retrying', 'sending'].includes(pendingItem.status)
  const fieldLocked = sendState === 'sending' || queuedSend
  const history = historyQuery.data?.pages.flatMap((page) => page.attempts) ?? []
  // The API pages newest first; a conversation reads the other way round.
  const ordered = [...history].reverse()
  const shown = showEveryTurn ? ordered : ordered.slice(-VISIBLE_TURNS)
  const hasEarlier = ordered.length > shown.length || historyQuery.hasNextPage
  const messages: ChatMessageView[] = shown.flatMap((attempt) => {
    const at = chatTime(attempt.serverReceivedAt)
    const dateLabel = chatDate(attempt.serverReceivedAt)
    const answered: ChatMessageView = {
      id: `answer:${attempt.attemptId}`,
      author: 'student',
      own: true,
      at,
      dateLabel,
      text: attempt.displayAnswer || 'Пустой ответ',
      delivery: 'sent',
    }
    const checked: ChatMessageView = {
      id: `check:${attempt.attemptId}`,
      author: 'bot',
      at,
      dateLabel,
      text: testAttemptReply(attempt),
    }
    const verdict = testAttemptVerdict(attempt.outcome)
    if (verdict) checked.verdict = verdict
    return [answered, checked]
  })
  if (queuedSend && pendingItem) {
    messages.push({
      id: `queued:${pendingItem.id}`,
      author: 'student',
      own: true,
      at: chatTime(pendingItem.createdAtClient),
      dateLabel: chatDate(pendingItem.createdAtClient),
      text: pendingItem.payload.request.displayAnswer,
      delivery: pendingItem.status === 'sending' ? 'sending' : 'queued',
    })
  }

  return (
    <section aria-label="Ваш ответ" className="mt-4 space-y-3 border-t border-border pt-4">
      {hasEarlier ? (
        <Button
          disabled={historyQuery.isFetchingNextPage}
          onClick={() => {
            if (!showEveryTurn) setShowEveryTurn(true)
            else void historyQuery.fetchNextPage()
          }}
          size="sm"
          variant="ghost"
        >
          {historyQuery.isFetchingNextPage ? 'Загружаем…' : 'Показать более ранние ответы'}
        </Button>
      ) : null}

      <TaskChat emptyLabel="Отправьте ответ — проверка придёт сразу." messages={messages} />

      {!closed && incompatibleDraft ? (
        <Alert tone="warning">
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Условие изменилось</AlertTitle>
            <AlertDescription>
              Ответ к предыдущей версии сохранён отдельно и не перенесён автоматически.
            </AlertDescription>
            <Button className="mt-2" onClick={restoreOldDraft} size="sm" variant="outline">
              Перенести только текст ответа
            </Button>
          </AlertContent>
        </Alert>
      ) : null}

      {!closed && storageError ? (
        <Alert role="alert" tone="danger">
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Черновик сейчас не сохраняется</AlertTitle>
            <AlertDescription>
              Не закрывайте страницу до отправки. Если возможно, освободите место в браузере и
              измените ответ ещё раз.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {sendError && sendState !== 'queued' ? (
        <Alert role="alert" tone={sendState === 'conflict' ? 'warning' : 'danger'}>
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>
              {sendState === 'conflict' ? 'Нужно обновить задачу' : 'Ответ не отправлен'}
            </AlertTitle>
            <AlertDescription>{sendError}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {closed ? (
        <p className="text-small text-muted-foreground">Приём ответов завершён.</p>
      ) : queuedSend ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface-subtle px-3 py-2 font-sans">
          <CloudOff aria-hidden="true" className="size-4 text-muted-foreground" />
          <p className="min-w-0 flex-1 text-small text-muted-foreground">
            {pendingItem?.status === 'sending'
              ? 'Отправляем…'
              : (sendError ?? submissionFailureMessage(undefined, pendingItem?.lastError))}
          </p>
          {pendingItem?.status !== 'sending' ? (
            <Button onClick={() => void deliver()} size="sm" variant="outline">
              Повторить
            </Button>
          ) : null}
        </div>
      ) : (
        <ChatComposer
          {...(receipt && !receipt.attempts.unlimited
            ? {
                hint: `Осталось попыток: ${receipt.attempts.remainingThisHour ?? '—'} в этот час, ${receipt.attempts.remainingToday ?? '—'} сегодня.`,
              }
            : {})}
          onSend={() => void submit()}
          sendDisabled={!answer.trim()}
          sending={sendState === 'sending'}
          sendLabel="Проверить"
        >
          <TestAnswer
            key={`${identity}:${editorEpoch}`}
            defaultValue={answer}
            disabled={fieldLocked}
            onChange={saveAnswer}
            showFormatError={showFormatError}
            spec={spec}
          />
        </ChatComposer>
      )}
    </section>
  )
}
