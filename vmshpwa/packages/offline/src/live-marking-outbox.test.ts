import 'fake-indexeddb/auto'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiResponseError, type LiveCommand, type LiveReceipt } from '@vmsh/contracts'
import { LiveMarkingDatabase, LiveMarkingQueue } from './live-marking-outbox'

const databases: LiveMarkingDatabase[] = []
const queues: LiveMarkingQueue[] = []
const context = {
  mode: 'zoom' as const,
  contextId: 'session-1',
  lessonId: 'gl-1',
  studentId: 'u-1',
}
const command = (problemId = 'p-1'): Extract<LiveCommand, { kind: 'mark' }> => ({
  kind: 'mark',
  operationId: crypto.randomUUID(),
  context,
  studentId: 'u-1',
  problemId,
  expectedVersion: 0,
  value: 'plus',
})
const receipt: LiveReceipt = {
  schemaVersion: 1,
  requestId: 'r',
  operationId: 'op-1',
  replayed: false,
  state: {
    kind: 'mark',
    studentId: 'u-1',
    problemId: 'p-1',
    version: 1,
    symbol: '+',
    verdict: 18,
    teacherId: 't-1',
    updatedAt: '2026-09-09',
  },
}
async function create(send = vi.fn().mockResolvedValue(receipt), database?: LiveMarkingDatabase) {
  const db =
    database ?? new LiveMarkingDatabase({ instance: `live-test-${crypto.randomUUID()}` }, 'a-1')
  if (!database) databases.push(db)
  const received = vi.fn()
  const queue = new LiveMarkingQueue(db, send, received)
  queues.push(queue)
  await queue.hydrate()
  return { queue, send, received, db }
}
afterEach(async () => {
  queues.forEach((q) => q.stop())
  queues.length = 0
  await Promise.all(databases.map((d) => d.delete()))
  databases.length = 0
  vi.useRealTimers()
})
describe('live-marking.md: durable two-second decision cycle', () => {
  it('does not write a fast full cycle, including over an existing plus', async () => {
    const { queue, send, db } = await create()
    const plus = { ...command(), expectedVersion: 12 }
    queue.cycle(plus)
    queue.cycle(plus)
    queue.cycle(plus)
    await queue.flush()
    expect(send).not.toHaveBeenCalled()
    expect(queue.getSnapshot().entries).toHaveLength(0)
    await vi.waitFor(async () => expect(await db.entries.count()).toBe(0))
  })
  it('waits two seconds since the last click then commits the selected minus', async () => {
    const { queue, send } = await create()
    vi.useFakeTimers({ toFake: ['Date'] })
    const start = Date.now()
    const input = command()
    queue.cycle(input)
    vi.setSystemTime(start + 1000)
    queue.cycle(input)
    vi.setSystemTime(start + 2999)
    await queue.flush(false)
    expect(send).not.toHaveBeenCalled()
    vi.setSystemTime(start + 3000)
    await queue.flush(false)
    expect(send).toHaveBeenCalledExactlyOnceWith({ ...input, value: 'minus' })
  })
  it('flushes the previous cell on a different cell selection', async () => {
    const { queue, send } = await create()
    const first = command()
    queue.cycle(first)
    queue.cycle(command('p-2'))
    await vi.waitFor(() => expect(send).toHaveBeenCalledExactlyOnceWith(first))
    expect(queue.getSnapshot().entries[0]?.command).toMatchObject({ problemId: 'p-2' })
  })
  it('uses the same idempotency key after a lost server response', async () => {
    const send = vi.fn().mockRejectedValueOnce(new TypeError('network')).mockResolvedValue(receipt)
    const { queue } = await create(send)
    const input = command()
    queue.cycle(input)
    await queue.flush()
    await queue.flush()
    expect(send).toHaveBeenNthCalledWith(1, input)
    expect(send).toHaveBeenNthCalledWith(2, input)
    expect(queue.getSnapshot().entries).toHaveLength(0)
  })
  it('retains conflicts until an explicit choice and does not silently rebase', async () => {
    const conflict = new ApiResponseError(409, {
      error: { code: 'live_marking_conflict', message: 'changed', requestId: 'r' },
    })
    const send = vi.fn().mockRejectedValue(conflict)
    const { queue } = await create(send)
    queue.cycle(command())
    await queue.flush()
    await queue.flush()
    expect(send).toHaveBeenCalledOnce()
    expect(queue.getSnapshot().entries[0]?.status).toBe('conflict')
    const id = queue.getSnapshot().entries[0]!.id
    send.mockResolvedValue(receipt)
    queue.retry(id, 7)
    await vi.waitFor(() => expect(send).toHaveBeenCalledTimes(2))
    expect(send.mock.calls[1]?.[0]).toMatchObject({ expectedVersion: 7 })
    expect(send.mock.calls[1]?.[0].operationId).not.toBe(id)
  })
  it('restores an unsent draft after reload and scopes storage by owner/runtime', async () => {
    const { queue, db } = await create()
    queue.cycle(command())
    await vi.waitFor(async () => expect(await db.entries.count()).toBe(1))
    queue.stop()
    const restored = await create(undefined, db)
    expect(restored.queue.getSnapshot().entries[0]?.phase).toBe(1)
    const other = new LiveMarkingDatabase({ instance: 'different' }, 'a-2')
    databases.push(other)
    expect(await other.entries.count()).toBe(0)
    await restored.queue.flush()
    expect(restored.send).toHaveBeenCalledOnce()
  })
  it('undoes local decisions before they reach the server', async () => {
    const { queue, send } = await create()
    const input = command()
    queue.cycle(input)
    queue.cycle(input)
    expect(queue.undoLocal('session-1')).toBe(true)
    expect(queue.getSnapshot().entries[0]?.command).toMatchObject({ value: 'plus' })
    expect(queue.undoLocal('session-1')).toBe(true)
    await queue.flush()
    expect(send).not.toHaveBeenCalled()
  })
})

it('does not rehydrate a stale sending record when an effect restarts', async () => {
  let complete: (value: LiveReceipt) => void = () => undefined
  const send = vi.fn(
    () =>
      new Promise<LiveReceipt>((resolve) => {
        complete = resolve
      }),
  )
  const { queue, db } = await create(send)
  queue.cycle(command())
  const pending = queue.flush()
  await vi.waitFor(() => expect(send).toHaveBeenCalledOnce())
  queue.stop()
  await queue.hydrate()
  complete(receipt)
  await pending
  await queue.flush()
  expect(send).toHaveBeenCalledOnce()
  expect(queue.getSnapshot().entries).toHaveLength(0)
  expect(await db.entries.count()).toBe(0)
})

it('undoes the second attendance click to the first pending state', async () => {
  const { queue, send } = await create()
  const input = {
    kind: 'attendance' as const,
    operationId: crypto.randomUUID(),
    context: { mode: 'school' as const, contextId: 'event-1', roomId: 'r-1' },
    studentId: 'u-1',
    expectedVersion: 2,
    value: 'absent' as const,
  }
  queue.cycle(input, 'present')
  queue.cycle(input, 'present')
  expect(queue.getSnapshot().entries[0]?.command).toMatchObject({ value: 'unmarked' })
  queue.undoLocal('event-1')
  await queue.flush()
  expect(send).toHaveBeenCalledExactlyOnceWith(input)
})
