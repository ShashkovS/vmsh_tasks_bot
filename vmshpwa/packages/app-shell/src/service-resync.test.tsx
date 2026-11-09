import { QueryObserver } from '@tanstack/react-query'
import { act, cleanup } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import type * as Contracts from '@vmsh/contracts'
import type { ServiceAvailability } from '@vmsh/contracts'
import { AppProviders, createAppQueryClient } from './providers'
import { resyncActiveQueries } from './query-resync'

const availability = vi.hoisted(
  (): {
    snapshot: ServiceAvailability
    listeners: Set<() => void>
  } => ({
    snapshot: { state: 'ready', since: 0, prolonged: false },
    listeners: new Set<() => void>(),
  }),
)
vi.mock('@vmsh/contracts', async (importOriginal) => ({
  ...(await importOriginal<typeof Contracts>()),
  serviceAvailabilitySnapshot: () => availability.snapshot,
  subscribeServiceAvailability: (listener: () => void) => {
    availability.listeners.add(listener)
    return () => availability.listeners.delete(listener)
  },
}))

afterEach(() => {
  cleanup()
  availability.listeners.clear()
  availability.snapshot = { state: 'ready', since: 0, prolonged: false }
})

it('joins a pending WS/online wave when the service becomes ready', async () => {
  const client = createAppQueryClient()
  const releases: (() => void)[] = []
  const read = vi.fn(() => new Promise<string>((resolve) => releases.push(() => resolve('fresh'))))
  const unsubscribes = Array.from({ length: 6 }, (_, index) =>
    new QueryObserver(client, {
      queryKey: ['service-resync', index],
      queryFn: read,
      initialData: 'old',
      staleTime: Infinity,
    }).subscribe(() => undefined),
  )
  render(
    <AppProviders queryClient={client}>
      <p>Shell</p>
    </AppProviders>,
  )
  act(() => {
    availability.snapshot = { state: 'reconnecting', since: 1, prolonged: false }
    availability.listeners.forEach((listener) => listener())
  })
  const pending = resyncActiveQueries(client)
  expect(read).toHaveBeenCalledTimes(4)
  act(() => {
    availability.snapshot = { state: 'ready', since: 0, prolonged: false }
    availability.listeners.forEach((listener) => listener())
  })
  expect(read).toHaveBeenCalledTimes(4)
  releases.splice(0).forEach((release) => release())
  await vi.waitFor(() => expect(read).toHaveBeenCalledTimes(6))
  releases.splice(0).forEach((release) => release())
  await pending
  expect(read).toHaveBeenCalledTimes(6)
  unsubscribes.forEach((unsubscribe) => unsubscribe())
  client.clear()
})
