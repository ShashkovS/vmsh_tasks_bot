import { Dexie, type Table } from 'dexie'
import { useEffect, useRef, useState } from 'react'

/** Account-isolated binary drafts; docs/organizer-questions.md.
 * Like written-submission-draft.ts, persist ArrayBuffers for WebKit, not Files.
 */
export interface OrganizerDraft {
  key: string
  text: string
  childId: string | null
  photos: Blob[]
  uploadedIds: (string | null)[]
  idempotencyKey: string
}
type StoredDraft = Omit<OrganizerDraft, 'photos'> & { photos: { id: string; type: string }[] }
class OrganizerDraftDatabase extends Dexie {
  drafts!: Table<StoredDraft, string>
  photos!: Table<{ id: string; bytes: ArrayBuffer }, string>
  constructor(name: string) {
    super(name)
    this.version(1).stores({ drafts: 'key', photos: 'id' })
  }
}
export function useOrganizerDraft(namespace: string, key: string) {
  const empty = (): OrganizerDraft => ({
    key,
    text: '',
    childId: null,
    photos: [],
    uploadedIds: [],
    idempotencyKey: crypto.randomUUID(),
  })
  const [draft, setDraft] = useState<OrganizerDraft>(empty)
  const [ready, setReady] = useState(false)
  const [saved, setSaved] = useState(false)
  const [unavailable, setUnavailable] = useState(false)
  const database = useRef<OrganizerDraftDatabase | null>(null)
  const writes = useRef(Promise.resolve())
  const photoIds = useRef(new WeakMap<Blob, string>())
  const revision = useRef(0)
  useEffect(() => {
    let active = true
    const db = new OrganizerDraftDatabase(`vmsh:${namespace}:organizer-drafts`)
    database.current = db
    void db.drafts
      .get(key)
      .then(async (value) => {
        if (!value) return
        const photos: Blob[] = []
        for (const item of value.photos) {
          const stored = await db.photos.get(item.id)
          if (!stored) throw new Error('Missing local photograph')
          const blob = new Blob([stored.bytes], { type: item.type })
          photoIds.current.set(blob, item.id)
          photos.push(blob)
        }
        if (active) setDraft({ ...value, photos })
      })
      .catch(() => {
        if (active) setUnavailable(true)
      })
      .finally(() => {
        if (active) setReady(true)
      })
    return () => {
      active = false
      void writes.current.finally(() => db.close())
    }
  }, [namespace, key])
  const update = (next: OrganizerDraft) => {
    setDraft(next)
    setSaved(false)
    const currentRevision = ++revision.current
    const db = database.current
    writes.current = writes.current.then(async () => {
      try {
        if (!db) throw new Error('Draft storage unavailable')
        const additions: { id: string; bytes: ArrayBuffer }[] = []
        const photos: { id: string; type: string; blob: Blob }[] = []
        for (const blob of next.photos) {
          let id = photoIds.current.get(blob)
          if (!id) {
            id = crypto.randomUUID()
            additions.push({ id, bytes: await blob.arrayBuffer() })
          }
          photos.push({ id, type: blob.type, blob })
        }
        await db.transaction('rw', db.drafts, db.photos, async () => {
          const old = await db.drafts.get(key)
          await db.photos.bulkPut(additions)
          await db.drafts.put({ ...next, photos: photos.map(({ id, type }) => ({ id, type })) })
          const retained = new Set(photos.map((photo) => photo.id))
          await db.photos.bulkDelete(
            (old?.photos ?? []).filter((photo) => !retained.has(photo.id)).map((photo) => photo.id),
          )
        })
        for (const photo of photos) photoIds.current.set(photo.blob, photo.id)
        if (revision.current === currentRevision) {
          setSaved(true)
          setUnavailable(false)
        }
      } catch {
        setUnavailable(true)
      }
    })
  }
  const clear = async () => {
    await writes.current
    try {
      const db = database.current
      if (!db) throw new Error('Draft storage unavailable')
      await db.transaction('rw', db.drafts, db.photos, async () => {
        const previous = await db.drafts.get(key)
        await db.photos.bulkDelete((previous?.photos ?? []).map((photo) => photo.id))
        await db.drafts.delete(key)
      })
    } catch {
      setUnavailable(true)
    }
    setDraft(empty())
    setSaved(false)
  }
  return { draft, update, clear, ready, saved, unavailable }
}
