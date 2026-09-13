import { useRef, useState } from 'react'
import { useAuthenticatedPrincipal, useAuthentication, type SupportClient } from '@vmsh/app-shell'
import { useOrganizerDraft } from '@vmsh/offline'
import { QuestionPhotoPicker, SupportComposer, type SupportComposerProps } from '@vmsh/product'

/** Photo drafts share binary storage mechanics with organizer questions; docs/question-photos.md. */
export function StudentPhotoSupportComposer({
  client,
  photoDraftKey,
  onSubmit,
  ...props
}: Omit<SupportComposerProps, 'onSubmit'> & {
  client: SupportClient
  photoDraftKey: string
  onSubmit: (photoIds: string[], clearPhotos: () => Promise<void>) => Promise<void>
}) {
  const principal = useAuthenticatedPrincipal()
  const auth = useAuthentication()
  const editor = useOrganizerDraft(
    `${auth.client.runtime.instance}:student:${principal.accountId}:support`,
    photoDraftKey,
  )
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const locked = useRef(false)
  const submit = async () => {
    if (locked.current) return
    locked.current = true
    setUploading(true)
    setError('')
    try {
      const ids: string[] = []
      for (const [index, photo] of editor.draft.photos.entries()) {
        if (!client.uploadPhoto) throw new Error('Photo uploads unavailable')
        const id = editor.draft.uploadedIds[index] ?? (await client.uploadPhoto(photo))
        ids.push(id)
        editor.update({ ...editor.draft, uploadedIds: [...ids] })
      }
      await onSubmit(ids, editor.clear)
    } catch {
      setError(
        'Не удалось отправить вопрос. Текст и фотографии сохранены в форме. Повторите отправку.',
      )
    } finally {
      locked.current = false
      setUploading(false)
    }
  }
  return (
    <SupportComposer
      {...props}
      busy={props.busy || uploading}
      disabled={props.disabled || !editor.ready}
      saveState={
        editor.unavailable
          ? 'unavailable'
          : editor.draft.photos.length && !editor.saved
            ? 'idle'
            : (props.saveState ?? 'idle')
      }
      error={error || props.error || null}
      onSubmit={() => void submit()}
      attachments={(action) => (
        <QuestionPhotoPicker
          action={action}
          photos={editor.draft.photos}
          disabled={props.busy || uploading || !editor.ready}
          onChange={(photos, removedIndex) =>
            editor.update({
              ...editor.draft,
              photos,
              uploadedIds:
                removedIndex === undefined
                  ? editor.draft.uploadedIds
                  : editor.draft.uploadedIds.filter((_, i) => i !== removedIndex),
            })
          }
        />
      )}
    />
  )
}
