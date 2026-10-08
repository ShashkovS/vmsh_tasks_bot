import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it, vi } from 'vitest'

import feedFixture from '@vmsh/contracts/fixtures/news/feed.v1.json'
import { newsFeedResponseSchema } from '@vmsh/contracts'

import { VmshOfflineDatabase } from './database'
import { createOfflineNewsClient, type CacheableNewsClient } from './news-cache'

const databases = new Set<VmshOfflineDatabase>()
const feed = newsFeedResponseSchema.parse(feedFixture)

afterEach(async () => {
  await Promise.all(
    [...databases].map(async (database) => {
      database.close()
      await database.delete()
    }),
  )
  databases.clear()
})

function database(audience: 'student' | 'family', instance: string) {
  const result = new VmshOfflineDatabase({ audience, instance })
  databases.add(result)
  return result
}

function client(list: CacheableNewsClient['list']): CacheableNewsClient {
  return {
    list,
    post: vi.fn(() => Promise.reject(new TypeError('offline'))),
  }
}

describe('offline news cache', () => {
  it('serves a cached feed and its detail after a network failure', async () => {
    const target = database('student', 'news-offline')
    const online = client(vi.fn(() => Promise.resolve(feed)))
    const first = createOfflineNewsClient(online, target, 'account.student-one')
    await first.list()

    const offline = createOfflineNewsClient(
      client(vi.fn(() => Promise.reject(new TypeError('offline')))),
      target,
      'account.student-one',
    )
    await expect(offline.list()).resolves.toEqual(feed)
    await expect(offline.post('news.course-41')).resolves.toMatchObject({
      item: { postId: 'news.course-41' },
    })
  })

  it('does not cross account or Student/Family database boundaries', async () => {
    const student = database('student', 'news-owner')
    const family = database('family', 'news-owner')
    await createOfflineNewsClient(
      client(vi.fn(() => Promise.resolve(feed))),
      student,
      'account.student-one',
    ).list()
    const unavailable = client(vi.fn(() => Promise.reject(new TypeError('offline'))))

    await expect(
      createOfflineNewsClient(unavailable, student, 'account.student-two').list(),
    ).rejects.toThrow('offline')
    await expect(
      createOfflineNewsClient(unavailable, family, 'account.student-one').list(),
    ).rejects.toThrow('offline')
  })

  it('does not replace an API or contract error with stale data', async () => {
    const target = database('student', 'news-errors')
    await createOfflineNewsClient(
      client(vi.fn(() => Promise.resolve(feed))),
      target,
      'account.student-one',
    ).list()
    const denied = new Error('forbidden')

    await expect(
      createOfflineNewsClient(
        client(vi.fn(() => Promise.reject(denied))),
        target,
        'account.student-one',
      ).list(),
    ).rejects.toBe(denied)
  })
})
