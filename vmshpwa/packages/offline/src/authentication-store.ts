import { z } from 'zod'

import {
  authContextSchema,
  principalSchema,
  publicIdSchema,
  type AuthContext,
} from '@vmsh/contracts'

import {
  offlineAudienceSchema,
  type CachedAuthenticationSnapshot,
  type OfflineAudience,
  type VmshOfflineDatabase,
} from './database'

/**
 * Secret-free identity envelope for owner-scoped cold-offline reading.
 * It deliberately excludes the session ID, cookies and credentials. See
 * Phase 3 in `dev/development-plan/07-phase-3-student-reading.md`.
 */
export const offlineAuthenticationSnapshotSchema = z
  .object({
    schemaVersion: z.literal(1),
    audience: offlineAudienceSchema,
    ownerId: publicIdSchema,
    principal: principalSchema,
    sessionExpiresAt: z.iso.datetime(),
    cachedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((snapshot, context) => {
    if (snapshot.principal.audience !== snapshot.audience) {
      context.addIssue({
        code: 'custom',
        message: 'Offline principal audience must match its database audience',
        path: ['principal', 'audience'],
      })
    }
    if (snapshot.principal.accountId !== snapshot.ownerId) {
      context.addIssue({
        code: 'custom',
        message: 'Offline principal owner must match its account',
        path: ['ownerId'],
      })
    }
  })
export type OfflineAuthenticationSnapshot = z.infer<typeof offlineAuthenticationSnapshotSchema>

export interface OfflineAuthenticationStore {
  read(): Promise<OfflineAuthenticationSnapshot | null>
  save(context: AuthContext): Promise<OfflineAuthenticationSnapshot>
  clear(): Promise<void>
}

export interface OfflineAuthenticationStoreOptions {
  now?: () => Date
}

function record(snapshot: OfflineAuthenticationSnapshot): CachedAuthenticationSnapshot {
  return {
    key: 'current',
    ownerId: snapshot.ownerId,
    expiresAt: snapshot.sessionExpiresAt,
    cachedAt: snapshot.cachedAt,
    payload: snapshot,
  }
}

async function clearOwner(database: VmshOfflineDatabase, ownerId: string): Promise<void> {
  await Promise.all([
    database.documents.where('ownerId').equals(ownerId).delete(),
    database.outbox.where('ownerId').equals(ownerId).delete(),
    database.writtenDraftPhotos.where('ownerId').equals(ownerId).delete(),
  ])
}

const ownerScopedTables = (database: VmshOfflineDatabase) =>
  [
    database.authentication,
    database.documents,
    database.outbox,
    database.writtenDraftPhotos,
  ] as const

export function createOfflineAuthenticationStore(
  database: VmshOfflineDatabase,
  audience: OfflineAudience,
  options: OfflineAuthenticationStoreOptions = {},
): OfflineAuthenticationStore {
  const expectedAudience = offlineAudienceSchema.parse(audience)
  const now = options.now ?? (() => new Date())

  return {
    async read() {
      const stored = await database.authentication.get('current')
      if (!stored) return null
      const parsed = offlineAuthenticationSnapshotSchema.safeParse(stored.payload)
      const snapshot = parsed.success ? parsed.data : null
      const invalid =
        snapshot === null ||
        snapshot.audience !== expectedAudience ||
        stored.ownerId !== snapshot.ownerId ||
        stored.expiresAt !== snapshot.sessionExpiresAt ||
        stored.cachedAt !== snapshot.cachedAt ||
        Date.parse(snapshot.sessionExpiresAt) <= now().getTime()
      if (!invalid) return snapshot

      await database.transaction('rw', ownerScopedTables(database), async () => {
        if (typeof stored.ownerId === 'string' && stored.ownerId !== '') {
          await clearOwner(database, stored.ownerId)
        }
        await database.authentication.delete('current')
      })
      return null
    },

    async save(context) {
      const authenticated = authContextSchema.parse(context)
      if (authenticated.principal.audience !== expectedAudience) {
        throw new TypeError('Offline authentication audience does not match the context')
      }
      const snapshot = offlineAuthenticationSnapshotSchema.parse({
        schemaVersion: 1,
        audience: expectedAudience,
        ownerId: authenticated.principal.accountId,
        principal: authenticated.principal,
        sessionExpiresAt: authenticated.policy.sessionExpiresAt,
        cachedAt: now().toISOString(),
      })
      if (Date.parse(snapshot.sessionExpiresAt) <= now().getTime()) {
        throw new TypeError('Expired authentication cannot unlock an offline cache')
      }

      await database.transaction('rw', ownerScopedTables(database), async () => {
        const previous = await database.authentication.get('current')
        if (previous && previous.ownerId !== snapshot.ownerId) {
          await clearOwner(database, previous.ownerId)
        }
        await database.authentication.put(record(snapshot))
      })
      return snapshot
    },

    async clear() {
      await database.transaction('rw', ownerScopedTables(database), async () => {
        const current = await database.authentication.get('current')
        if (current) await clearOwner(database, current.ownerId)
        await database.authentication.delete('current')
      })
    },
  }
}
