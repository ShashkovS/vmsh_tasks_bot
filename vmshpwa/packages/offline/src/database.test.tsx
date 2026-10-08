import 'fake-indexeddb/auto'

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createBrowserStorageNamespace } from '@vmsh/contracts'

import {
  OfflineDatabaseProvider,
  OfflineDatabaseBlockedError,
  OfflineDatabaseClosedError,
  OfflineDatabaseOpenTimeoutError,
  VmshOfflineDatabase,
  offlineDatabaseName,
  openOfflineDatabaseWithDeadline,
  useOfflineDatabase,
  type OutboxItem,
} from './index'

const databases = new Set<VmshOfflineDatabase>()

afterEach(async () => {
  vi.useRealTimers()
  cleanup()
  await Promise.all(
    [...databases].map(async (database) => {
      database.close()
      await database.delete()
    }),
  )
  databases.clear()
})

function track(database: VmshOfflineDatabase): VmshOfflineDatabase {
  databases.add(database)
  return database
}

function outboxItem(ownerId: string): OutboxItem {
  return {
    id: 'same-logical-id',
    idempotencyKey: `idempotency-${ownerId}`,
    ownerId,
    kind: 'written-answer',
    createdAtClient: '2026-07-27T12:00:00.000Z',
    updatedAtClient: '2026-07-27T12:00:00.000Z',
    timezoneOffsetMinutes: -180,
    payloadHash: `sha256:${ownerId.padEnd(16, '0')}`,
    status: 'queued',
    attempts: 0,
    payload: { text: ownerId },
  }
}

function DatabaseProbe({ onReady }: { onReady: (database: VmshOfflineDatabase) => void }) {
  const database = useOfflineDatabase()
  onReady(database)
  return <p>База готова: {database.name}</p>
}

describe('VmshOfflineDatabase isolation', () => {
  it('uses the exact canonical namespace as the Dexie database name', () => {
    const studentNamespace = createBrowserStorageNamespace({
      audience: 'student',
      instance: 'agent',
    })
    const familyNamespace = createBrowserStorageNamespace({ audience: 'family', instance: 'e2e' })
    expect(offlineDatabaseName({ audience: 'student', instance: 'agent' })).toBe(studentNamespace)
    expect(track(new VmshOfflineDatabase({ audience: 'family', instance: 'e2e' })).name).toBe(
      familyNamespace,
    )
  })

  it('keeps real IndexedDB records isolated by audience and runtime instance', async () => {
    const studentAgent = track(new VmshOfflineDatabase({ audience: 'student', instance: 'agent' }))
    const studentHuman = track(new VmshOfflineDatabase({ audience: 'student', instance: 'human' }))
    const familyAgent = track(new VmshOfflineDatabase({ audience: 'family', instance: 'agent' }))
    await Promise.all([studentAgent.open(), studentHuman.open(), familyAgent.open()])

    await Promise.all([
      studentAgent.outbox.put(outboxItem('student-agent')),
      studentHuman.outbox.put(outboxItem('student-human')),
      familyAgent.outbox.put(outboxItem('family-agent')),
    ])

    expect((await studentAgent.outbox.get('same-logical-id'))?.ownerId).toBe('student-agent')
    expect((await studentHuman.outbox.get('same-logical-id'))?.ownerId).toBe('student-human')
    expect((await familyAgent.outbox.get('same-logical-id'))?.ownerId).toBe('family-agent')
    expect(await Promise.all([...databases].map((database) => database.outbox.count()))).toEqual([
      1, 1, 1,
    ])
  })

  it('opens before exposing context and closes the same database on unmount', async () => {
    const expectedNamespace = createBrowserStorageNamespace({
      audience: 'student',
      instance: 'agent',
    })
    let openedDatabase: VmshOfflineDatabase | undefined
    const view = render(
      <StrictMode>
        <OfflineDatabaseProvider
          errorFallback={() => <p>Не удалось открыть локальную базу</p>}
          loadingFallback={<p>Открываем локальную базу</p>}
          runtime={{ audience: 'student', instance: 'agent' }}
        >
          <DatabaseProbe
            onReady={(database) => {
              openedDatabase = database
              track(database)
            }}
          />
        </OfflineDatabaseProvider>
      </StrictMode>,
    )

    expect(screen.getByText('Открываем локальную базу')).not.toBeNull()
    expect(await screen.findByText(`База готова: ${expectedNamespace}`)).not.toBeNull()
    expect(openedDatabase?.isOpen()).toBe(true)

    view.unmount()
    await waitFor(() => expect(openedDatabase?.isOpen()).toBe(false))
  })

  it('rejects unsafe instance names before IndexedDB is opened', () => {
    expect(() => new VmshOfflineDatabase({ audience: 'student', instance: '../human' })).toThrow()
  })

  it('fails a blocked upgrade instead of leaving startup pending forever', async () => {
    const database = track(new VmshOfflineDatabase({ audience: 'student', instance: 'blocked' }))
    const neverOpens = new Promise<VmshOfflineDatabase>(() => undefined)
    vi.spyOn(database, 'open').mockReturnValue(
      neverOpens as unknown as ReturnType<VmshOfflineDatabase['open']>,
    )

    const opening = openOfflineDatabaseWithDeadline(database, 1_000)
    database.on.blocked.fire(new Event('blocked'))

    await expect(opening).rejects.toBeInstanceOf(OfflineDatabaseBlockedError)
  })

  it('bounds an IndexedDB open that never settles', async () => {
    vi.useFakeTimers()
    const database = track(new VmshOfflineDatabase({ audience: 'family', instance: 'timeout' }))
    const neverOpens = new Promise<VmshOfflineDatabase>(() => undefined)
    vi.spyOn(database, 'open').mockReturnValue(
      neverOpens as unknown as ReturnType<VmshOfflineDatabase['open']>,
    )

    const opening = openOfflineDatabaseWithDeadline(database, 500)
    const rejection = expect(opening).rejects.toBeInstanceOf(OfflineDatabaseOpenTimeoutError)
    await vi.advanceTimersByTimeAsync(500)

    await rejection
  })

  it('preserves a rejected open and can retry the same database instance', async () => {
    const database = track(new VmshOfflineDatabase({ audience: 'student', instance: 'retry' }))
    const openFailure = new Error('Synthetic IndexedDB open failure')
    vi.spyOn(database, 'open').mockRejectedValueOnce(openFailure)

    await expect(openOfflineDatabaseWithDeadline(database)).rejects.toBe(openFailure)
    await expect(openOfflineDatabaseWithDeadline(database)).resolves.toBeUndefined()
    expect(database.isOpen()).toBe(true)
  })

  it('returns to a recoverable error state after an unexpected database close', async () => {
    let openedDatabase: VmshOfflineDatabase | undefined
    render(
      <OfflineDatabaseProvider
        errorFallback={({ error }) => <p>{(error as Error).name}</p>}
        loadingFallback={<p>Открываем локальную базу</p>}
        runtime={{ audience: 'student', instance: 'closed' }}
      >
        <DatabaseProbe
          onReady={(database) => {
            openedDatabase = track(database)
          }}
        />
      </OfflineDatabaseProvider>,
    )
    await screen.findByText(/База готова:/)

    openedDatabase?.close({ disableAutoOpen: false })

    expect(await screen.findByText(OfflineDatabaseClosedError.name)).not.toBeNull()
  })
})
