import { useState } from 'react'

import { normalizeLessonVideoUrl } from '@vmsh/product'
import { Button, Input, Label } from '@vmsh/ui'

function markdownTitle(value: string | null): string {
  return value === null
    ? ''
    : value.replaceAll('\\', '\\\\').replaceAll('[', '\\[').replaceAll(']', '\\]')
}

/** A small, explicit insertion surface. The submitted iframe is parsed as data. */
export function LessonVideoDialog({ onInsert }: { onInsert: (markdown: string) => void }) {
  const [source, setSource] = useState('')
  const [title, setTitle] = useState('')
  const [error, setError] = useState<string | null>(null)
  const insert = () => {
    try {
      const video = normalizeLessonVideoUrl(source, title)
      const canonical =
        video.provider === 'youtube'
          ? `https://www.youtube.com/watch?v=${video.videoId}${video.startSeconds ? `&t=${video.startSeconds}` : ''}`
          : `https://vkvideo.ru/video_ext.php?oid=${video.ownerId}&id=${video.videoId}${video.accessHash ? `&hash=${video.accessHash}` : ''}&hd=${video.hd}`
      onInsert(`\n\n::video[${markdownTitle(video.title)}](${canonical})\n`)
      setSource('')
      setTitle('')
      setError(null)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось разобрать видео')
    }
  }
  return (
    <div className="grid gap-2 rounded-md border border-border p-3">
      <p className="text-label font-medium">Видео</p>
      <Label>
        Ссылка YouTube/VK или iframe
        <Input onChange={(event) => setSource(event.target.value)} value={source} />
      </Label>
      <Label>
        Название (необязательно)
        <Input onChange={(event) => setTitle(event.target.value)} value={title} />
      </Label>
      <Button onClick={insert} size="sm" type="button" variant="outline">
        Вставить видео
      </Button>
      {error ? (
        <p className="text-caption text-status-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
