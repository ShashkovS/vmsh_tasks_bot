import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { maxRichFileBytes, richFileExtensions, type StaffRichFile } from '@vmsh/contracts'
import { Button } from '@vmsh/ui'
import { Paperclip } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { fileAttachmentMarkdown } from './file-attachment-markdown'

/** Authoring states shared by both editors; docs/rich-file-attachments.md. */
export function StaffFileUpload({
  disabled = false,
  onUpload,
  onInsert,
}: {
  disabled?: boolean
  onUpload: (file: File) => Promise<StaffRichFile>
  onInsert: (markdown: string) => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const insert = useRef(onInsert)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    insert.current = onInsert
  }, [onInsert])

  const upload = async (file: File) => {
    setError(null)
    if (
      !file.size ||
      file.size > maxRichFileBytes ||
      !richFileExtensions.some((extension) => file.name.toLowerCase().endsWith(`.${extension}`))
    ) {
      setError(t`Выберите непустой документ или архив до 50 МиБ поддерживаемого формата.`)
      return
    }
    setPending(true)
    try {
      const uploaded = await onUpload(file)
      insert.current(fileAttachmentMarkdown(uploaded))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t`Не удалось загрузить файл.`)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <input
          aria-label={t`Файл для прикрепления`}
          accept={richFileExtensions.map((extension) => `.${extension}`).join(',')}
          className="sr-only"
          disabled={disabled || pending}
          ref={input}
          tabIndex={-1}
          type="file"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ''
            if (file) void upload(file)
          }}
        />
        <Button
          disabled={disabled || pending}
          onClick={() => input.current?.click()}
          size="sm"
          type="button"
          variant="outline"
        >
          <Paperclip aria-hidden="true" />
          {pending ? t`Загружаем файл…` : t`Прикрепить файл`}
        </Button>
        <span className="text-caption text-muted-foreground">
          <Trans>PDF, документы, таблицы, презентации и архивы · до 50 МиБ</Trans>
        </span>
      </div>
      {pending ? (
        <p className="text-caption text-muted-foreground" role="status">
          <Trans>Дождитесь загрузки файла перед сохранением текста.</Trans>
        </p>
      ) : null}
      {error ? (
        <p className="text-caption text-status-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}
