import {
  newsFeedResponseSchema,
  newsPostResponseSchema,
  type NewsFeedResponse,
  type NewsPostResponse,
} from '@vmsh/contracts'

import type { VmshOfflineDatabase } from './database'
import { readOfflineDocument, writeOfflineDocument } from './document-cache'

interface NewsReadOptions {
  cursor?: string
  limit?: number
  signal?: AbortSignal
}

export interface CacheableNewsClient {
  list(options?: NewsReadOptions): Promise<NewsFeedResponse>
  post(postId: string, options?: { signal?: AbortSignal }): Promise<NewsPostResponse>
}

function feedDescriptor(ownerId: string, cursor?: string) {
  return {
    ownerId,
    kind: 'news-feed' as const,
    resourceParts: [cursor ?? 'first-page'],
  }
}

function postDescriptor(ownerId: string, postId: string) {
  return { ownerId, kind: 'news-post' as const, resourceParts: [postId] }
}

function feedVersion(feed: NewsFeedResponse): string {
  const first = feed.items[0]
  const last = feed.items.at(-1)
  return first && last
    ? `${first.postId}:${first.revision}:${last.postId}:${last.revision}:${feed.items.length}`
    : 'empty'
}

async function saveFeed(
  database: VmshOfflineDatabase,
  ownerId: string,
  cursor: string | undefined,
  feed: NewsFeedResponse,
): Promise<void> {
  try {
    await writeOfflineDocument(
      database,
      feedDescriptor(ownerId, cursor),
      feedVersion(feed),
      feed,
      newsFeedResponseSchema,
    )
    for (const item of feed.items) {
      await writeOfflineDocument(
        database,
        postDescriptor(ownerId, item.postId),
        String(item.revision),
        { schemaVersion: 1, item, requestId: feed.requestId },
        newsPostResponseSchema,
      )
    }
  } catch {
    // Offline caching is best-effort and must not hide a valid server response.
  }
}

/** Owner-scoped news cache for Student and Family PWA offline reading. */
export function createOfflineNewsClient(
  online: CacheableNewsClient,
  database: VmshOfflineDatabase,
  ownerId: string,
): CacheableNewsClient {
  return {
    async list(options = {}) {
      try {
        const feed = await online.list(options)
        await saveFeed(database, ownerId, options.cursor, feed)
        return feed
      } catch (error) {
        if (!(error instanceof TypeError)) throw error
        const cached = await readOfflineDocument(
          database,
          feedDescriptor(ownerId, options.cursor),
          newsFeedResponseSchema,
        )
        if (!cached) throw error
        return cached.data
      }
    },
    async post(postId, options = {}) {
      try {
        const response = await online.post(postId, options)
        try {
          await writeOfflineDocument(
            database,
            postDescriptor(ownerId, postId),
            String(response.item.revision),
            response,
            newsPostResponseSchema,
          )
        } catch {
          // Offline caching is best-effort.
        }
        return response
      } catch (error) {
        if (!(error instanceof TypeError)) throw error
        const cached = await readOfflineDocument(
          database,
          postDescriptor(ownerId, postId),
          newsPostResponseSchema,
        )
        if (!cached) throw error
        return cached.data
      }
    },
  }
}
