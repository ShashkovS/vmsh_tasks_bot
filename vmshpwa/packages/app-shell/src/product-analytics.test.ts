import { afterEach, describe, expect, it, vi } from 'vitest'

import { canonicalProductRoute, ProductAnalyticsTracker } from './product-analytics'

afterEach(() => vi.useRealTimers())

it('batches a route/action burst and flushes immediately before page hide', async () => {
  vi.useFakeTimers()
  const send = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 }))
  const tracker = new ProductAnalyticsTracker('student', '/student/api/v1', send)
  tracker.track('page.view', '/tasks/c-1')
  tracker.track('task.open', '/tasks/c-1', { type: 'problem', id: 'p-1' })
  expect(send).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(100)
  expect(send).toHaveBeenCalledTimes(1)
  expect(JSON.parse(send.mock.calls[0]![1]!.body as string).events).toHaveLength(2)
  tracker.track('written.submit', '/tasks/c-1')
  await tracker.flush()
  expect(send).toHaveBeenCalledTimes(2)
  await vi.advanceTimersByTimeAsync(200)
  expect(send).toHaveBeenCalledTimes(2)
})

it('bounds events received during a slow request and flushes after it completes', async () => {
  vi.useFakeTimers()
  let finish!: (value: Response) => void
  const send = vi
    .fn<typeof fetch>()
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    .mockResolvedValue(new Response(null, { status: 204 }))
  const tracker = new ProductAnalyticsTracker('student', '/student/api/v1', send)
  tracker.track('page.view', '/')
  await vi.advanceTimersByTimeAsync(100)
  for (let i = 0; i < 100; i++) tracker.track('task.open', '/')
  await vi.advanceTimersByTimeAsync(100)
  expect(send).toHaveBeenCalledTimes(1)
  finish(new Response(null, { status: 204 }))
  await vi.advanceTimersByTimeAsync(100)
  expect(send).toHaveBeenCalledTimes(2)
  expect(JSON.parse(send.mock.calls[1]![1]!.body as string).events).toHaveLength(20)
})

describe('product analytics route canonicalization', () => {
  it.each(['н', 'п', 'э', '%D0%BD', '%D0%BF', '%D1%8D'])(
    'normalizes group %s to the ASCII route contract',
    (group) => {
      expect(canonicalProductRoute(`/tasks/vmsh/${group}/0?task=5`)).toBe('/tasks/vmsh/:id/:id')
    },
  )
  it('keeps a route shape but removes opaque IDs, query strings and hashes', () => {
    expect(canonicalProductRoute('/tasks/course.abc/group.def/5?answer=secret#solution')).toBe(
      '/tasks/:id/:id/:id',
    )
  })

  it('does not turn a URL into telemetry route data', () => {
    expect(canonicalProductRoute('/news')).toBe('/news')
    expect(canonicalProductRoute('/')).toBe('/')
  })
})
