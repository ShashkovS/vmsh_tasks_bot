import Dexie, { type EntityTable } from 'dexie'
import { z } from 'zod'
import {
  ApiResponseError,
  createBrowserStorageNamespace,
  liveCommandSchema,
  type LiveCommand,
  type LiveReceipt,
  type RuntimeConfig,
} from '@vmsh/contracts'

// Staff owns a separate durable queue. See live-marking.md; no Student/Family
// database or service worker is reused, and only the authenticated owner opens it.
const entrySchema = z.object({
  id: z.string(),
  key: z.string(),
  command: liveCommandSchema,
  status: z.enum(['draft', 'queued', 'sending', 'conflict', 'failed']),
  steps: z.array(z.number().int()),
  phase: z.number().int(),
  createdAt: z.number(),
  dueAt: z.number(),
  error: z.string().optional(),
  attempted: z.boolean().optional(),
  beforeSymbol: z.string().optional(),
  targetSymbol: z.string().optional(),
})
export type LivePendingEntry = z.infer<typeof entrySchema>
export class LiveMarkingDatabase extends Dexie {
  entries!: EntityTable<LivePendingEntry, 'id'>
  constructor(runtime: Pick<RuntimeConfig, 'instance'>, ownerId: string) {
    super(
      `${createBrowserStorageNamespace({ audience: 'staff', instance: runtime.instance })}:live-marking:${ownerId}`,
    )
    this.version(1).stores({ entries: '&id, key, createdAt' })
  }
}
export function liveCommandKey(command: LiveCommand): string {
  const target = 'studentId' in command ? command.studentId : command.targetOperationId
  const problem = command.kind === 'mark' ? command.problemId : command.kind
  return `${command.context.mode}:${command.context.contextId}:${target}:${problem}`
}
export type LiveQueueSnapshot = {
  entries: readonly LivePendingEntry[]
  storageError: string | null
  ready: boolean
}
export class LiveMarkingQueue {
  private snapshot: LiveQueueSnapshot = { entries: [], storageError: null, ready: false }
  private listeners = new Set<() => void>()
  private persistence: Promise<unknown> = Promise.resolve()
  private timer: ReturnType<typeof setTimeout> | undefined
  private running = false
  private waiters: (() => void)[] = []
  private localUndo: { contextId: string; id: string; before?: LivePendingEntry | undefined }[] = []
  private stopped = false
  private hydration: Promise<void> | undefined
  constructor(
    private database: LiveMarkingDatabase,
    private send: (command: LiveCommand) => Promise<LiveReceipt>,
    private received: (receipt: LiveReceipt, command: LiveCommand) => void,
  ) {}
  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
  getSnapshot = () => this.snapshot
  private emit(entries = this.snapshot.entries) {
    this.snapshot = { ...this.snapshot, entries }
    this.listeners.forEach((listener) => listener())
  }
  private persist(entry: LivePendingEntry | undefined, id: string) {
    this.persistence = this.persistence
      .then(async () => {
        if (entry) await this.database.entries.put(entry)
        else await this.database.entries.delete(id)
      })
      .catch(() => {
        this.snapshot = {
          ...this.snapshot,
          storageError: 'Не удалось сохранить очередь на устройстве. Не закрывайте окно.',
        }
        this.emit()
      })
  }
  hydrate() {
    this.stopped = false
    this.schedule()
    return (this.hydration ??= this.load())
  }
  private async load() {
    try {
      const values = await this.database.entries.toArray()
      const entries = values
        .map((v) => entrySchema.parse(v))
        .map((entry): LivePendingEntry => ({
          ...entry,
          status: entry.status === 'sending' ? 'queued' : entry.status,
          attempted: entry.attempted ?? ['sending', 'queued'].includes(entry.status),
        }))
      this.snapshot = { entries, ready: true, storageError: null }
      this.emit()
      this.schedule()
    } catch {
      this.snapshot = {
        ...this.snapshot,
        ready: true,
        storageError: 'Очередь на устройстве недоступна.',
      }
      this.emit()
    }
  }
  private schedule(retryDelay = 0) {
    clearTimeout(this.timer)
    const actionable = this.snapshot.entries.filter((entry) =>
      ['draft', 'queued'].includes(entry.status),
    )
    if (!actionable.length) return
    const delay = Math.max(
      retryDelay,
      Math.min(
        ...actionable.map((entry) =>
          entry.status === 'queued' ? 0 : Math.max(0, entry.dueAt - Date.now()),
        ),
      ),
    )
    if (!this.stopped)
      this.timer = setTimeout(() => {
        void this.flush(false)
      }, delay)
  }
  stop() {
    this.stopped = true
    clearTimeout(this.timer)
  }
  // One click moves the draft cycle. A full unsent cycle deletes the operation.
  cycle(
    command: Extract<LiveCommand, { kind: 'mark' | 'attendance' }>,
    initialAttendance = 'unmarked',
    beforeSymbol?: string,
  ) {
    const key = liveCommandKey(command)
    const old = this.snapshot.entries.find((e) => e.key === key)
    if (old && (old.attempted || ['sending', 'conflict', 'failed'].includes(old.status))) return
    this.flushOther(key)
    this.localUndo.push({
      contextId: command.context.contextId,
      id: old?.id ?? command.operationId,
      before: old,
    })
    const phase = ((old?.phase ?? 0) + 1) % 3
    if (phase === 0) {
      if (old) {
        this.emit(this.snapshot.entries.filter((e) => e.id !== old.id))
        this.persist(undefined, old.id)
      }
      return
    }
    let nextCommand: LiveCommand = old?.command ?? command
    if (nextCommand.kind === 'mark')
      nextCommand = { ...nextCommand, value: phase === 1 ? 'plus' : 'minus' }
    if (nextCommand.kind === 'attendance') {
      const states = ['unmarked', 'present', 'absent'] as const
      nextCommand = {
        ...nextCommand,
        value: states[(states.indexOf(initialAttendance as (typeof states)[number]) + phase) % 3]!,
      }
    }
    const entry: LivePendingEntry = {
      id: old?.id ?? command.operationId,
      key,
      command: nextCommand,
      status: 'draft',
      steps: [...(old?.steps ?? []), old?.phase ?? 0],
      phase,
      createdAt: old?.createdAt ?? Date.now(),
      dueAt: Date.now() + 2000,
      beforeSymbol: old?.beforeSymbol ?? beforeSymbol,
    }
    this.emit([...this.snapshot.entries.filter((e) => e.id !== entry.id), entry])
    this.persist(entry, entry.id)
    this.schedule()
  }
  clearMark(
    command: Extract<LiveCommand, { kind: 'mark' }>,
    beforeSymbol: string,
    targetSymbol = '',
  ) {
    const key = liveCommandKey(command)
    if (this.snapshot.entries.some((entry) => entry.key === key)) return
    this.flushOther(key)
    const entry: LivePendingEntry = {
      id: command.operationId,
      key,
      command: { ...command, value: 'clear' },
      phase: 3,
      steps: [0],
      createdAt: Date.now(),
      dueAt: Date.now() + 2000,
      status: 'draft',
      beforeSymbol,
      targetSymbol,
    }
    this.localUndo.push({ contextId: command.context.contextId, id: entry.id })
    this.emit([...this.snapshot.entries, entry])
    this.persist(entry, entry.id)
    this.schedule()
  }
  private flushOther(key: string) {
    for (const entry of this.snapshot.entries)
      if (entry.key !== key && entry.status === 'draft')
        this.replace({ ...entry, status: 'queued' })
    void this.flush(false)
  }
  enqueueUndo(
    command: Extract<LiveCommand, { kind: 'undo' }>,
    preview?: { studentId: string; problemId: string; beforeSymbol: string; targetSymbol: string },
  ) {
    const entry: LivePendingEntry = {
      id: command.operationId,
      command,
      key: preview
        ? `${command.context.mode}:${command.context.contextId}:${preview.studentId}:${preview.problemId}`
        : liveCommandKey(command),
      status: 'queued',
      phase: 1,
      steps: [],
      createdAt: Date.now(),
      dueAt: Date.now(),
      beforeSymbol: preview?.beforeSymbol,
      targetSymbol: preview?.targetSymbol,
    }
    this.emit([...this.snapshot.entries, entry])
    this.persist(entry, entry.id)
  }
  private replace(entry: LivePendingEntry) {
    this.emit(this.snapshot.entries.map((e) => (e.id === entry.id ? entry : e)))
    this.persist(entry, entry.id)
  }
  discard(id: string, keepUndo = false) {
    if (!keepUndo) this.localUndo = this.localUndo.filter((step) => step.id !== id)
    this.emit(this.snapshot.entries.filter((e) => e.id !== id))
    this.persist(undefined, id)
  }
  retry(id: string, expectedVersion?: number) {
    const entry = this.snapshot.entries.find((e) => e.id === id)
    if (!entry) return
    let command = entry.command
    if (expectedVersion !== undefined && 'expectedVersion' in command)
      command = { ...command, expectedVersion, operationId: crypto.randomUUID() }
    this.discard(id)
    const next = {
      ...entry,
      id: command.operationId,
      command,
      status: 'queued' as const,
      error: undefined,
    }
    this.emit([...this.snapshot.entries, next])
    this.persist(next, next.id)
    void this.flush(false)
  }
  undoLocal(contextId: string): boolean {
    const reverseIndex = [...this.localUndo]
      .reverse()
      .findIndex((step) => step.contextId === contextId)
    const index = reverseIndex === -1 ? -1 : this.localUndo.length - 1 - reverseIndex
    if (index !== -1) {
      const step = this.localUndo[index]!
      const current = this.snapshot.entries.find((entry) => entry.id === step.id)
      // A lost response may already have committed. Resolve the original ID first.
      if (current?.attempted || current?.status === 'sending') return false
      this.localUndo.splice(index, 1)
      this.discard(step.id, true)
      if (step.before) {
        const restored = { ...step.before, status: 'draft' as const, dueAt: Date.now() + 2000 }
        this.emit([...this.snapshot.entries, restored])
        this.persist(restored, restored.id)
      }
      this.schedule()
      return true
    }
    const entry = [...this.snapshot.entries]
      .filter((e) => e.command.context.contextId === contextId)
      .sort((a, b) => b.dueAt - a.dueAt)[0]
    if (!entry) return false
    if (entry.attempted || entry.status === 'sending') return false
    if (
      entry.status === 'conflict' ||
      entry.status === 'failed' ||
      entry.phase === 1 ||
      entry.phase === 3
    ) {
      this.discard(entry.id)
      return true
    }
    if (entry.command.kind === 'mark')
      this.replace({
        ...entry,
        phase: 1,
        steps: [0],
        status: 'draft',
        dueAt: Date.now() + 2000,
        command: { ...entry.command, value: 'plus' },
      })
    else if (entry.command.kind === 'attendance') {
      const states = ['unmarked', 'present', 'absent'] as const
      this.replace({
        ...entry,
        phase: 1,
        steps: [0],
        status: 'draft',
        dueAt: Date.now() + 2000,
        command: {
          ...entry.command,
          value: states[(states.indexOf(entry.command.value) + 2) % 3]!,
        },
      })
    } else this.discard(entry.id)
    this.schedule()
    return true
  }
  canUndoLocal(contextId: string): boolean {
    return this.localUndo.some((step) => step.contextId === contextId)
  }
  async flush(force = true) {
    if (force)
      for (const entry of this.snapshot.entries)
        if (entry.status === 'draft') this.replace({ ...entry, status: 'queued' })
    if (this.running) {
      await new Promise<void>((resolve) => this.waiters.push(resolve))
      return
    }
    if (this.stopped || !this.snapshot.ready) return
    this.running = true
    let retryDelay = 0
    try {
      if (typeof navigator !== 'undefined' && !navigator.onLine) {
        for (const entry of this.snapshot.entries)
          if (entry.status === 'draft' && entry.dueAt <= Date.now())
            this.replace({ ...entry, status: 'queued' })
        retryDelay = 1000
        return
      }
      for (const candidate of [...this.snapshot.entries].sort(
        (a, b) => a.createdAt - b.createdAt,
      )) {
        const entry = this.snapshot.entries.find((e) => e.id === candidate.id)
        if (
          !entry ||
          !['queued', 'draft'].includes(entry.status) ||
          (entry.status === 'draft' && entry.dueAt > Date.now())
        )
          continue
        this.replace({ ...entry, status: 'sending', attempted: true })
        await this.persistence
        if (this.snapshot.storageError) {
          this.replace({ ...entry, status: 'failed', error: this.snapshot.storageError })
          break
        }
        try {
          const receipt = await this.send(entry.command)
          this.received(receipt, entry.command)
          this.localUndo = this.localUndo.filter((step) => step.id !== entry.id)
          this.discard(entry.id)
          await this.persistence
        } catch (error) {
          const status = error instanceof ApiResponseError ? error.status : 0
          this.replace({
            ...entry,
            attempted: !status || status >= 500,
            status:
              status === 409 ? 'conflict' : status >= 400 && status < 500 ? 'failed' : 'queued',
            error: error instanceof Error ? error.message : 'Не отправлено',
          })
          if (!status || status >= 500) {
            retryDelay = 1000
            break
          }
        }
      }
    } finally {
      this.running = false
      for (const resolve of this.waiters.splice(0)) resolve()
      if (this.snapshot.entries.length) this.schedule(retryDelay)
    }
  }
}
