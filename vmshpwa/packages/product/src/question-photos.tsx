import { t } from '@lingui/core/macro'
import { ZoomableFigure } from './zoomable-figure'
import { Camera, ImagePlus, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Button } from '@vmsh/ui'

/** Shared question attachment controls; docs/question-photos.md. */
export function QuestionPhotoPicker({
  photos,
  onChange,
  disabled = false,
  action,
  prepareFile,
  onPreparingChange,
}: {
  photos: Blob[]
  onChange: (photos: Blob[], removedIndex?: number) => void
  action?: ReactNode
  prepareFile?: (file: File, signal: AbortSignal) => Promise<Blob>
  onPreparingChange?: (preparing: boolean) => void
  disabled?: boolean
}) {
  const gallery = useRef<HTMLInputElement>(null)
  const camera = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<File[]>([])
  const controllers = useRef(new Map<File, AbortController>())
  const currentPhotos = useRef(photos)
  const currentOnChange = useRef(onChange)
  const active = useRef(true)
  useEffect(() => {
    currentPhotos.current = photos
    currentOnChange.current = onChange
  }, [photos, onChange])
  useEffect(() => {
    active.current = true
    const processing = controllers.current
    return () => {
      active.current = false
      for (const controller of processing.values()) controller.abort()
    }
  }, [])
  const select = async (input: HTMLInputElement) => {
    const files = Array.from(input.files ?? [])
    input.value = ''
    if (
      files.length + photos.length > 10 ||
      files.some(
        (file) =>
          file.size > 25 * 1024 * 1024 ||
          (!['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'].includes(
            file.type,
          ) &&
            !/\.hei[cf]$/i.test(file.name)),
      )
    ) {
      setError(
        t`Можно прикрепить до 10 фотографий JPEG, PNG, WebP или HEIC размером до 25 МиБ каждая.`,
      )
      return
    }
    setError('')
    if (!prepareFile) {
      onChange([...photos, ...files])
      return
    }
    for (const file of files) controllers.current.set(file, new AbortController())
    setPending(files)
    onPreparingChange?.(true)
    try {
      for (const file of files) {
        const controller = controllers.current.get(file)!
        if (controller.signal.aborted) {
          controllers.current.delete(file)
          continue
        }
        try {
          const prepared = await prepareFile(file, controller.signal)
          if (!controller.signal.aborted && active.current) {
            const next = [...currentPhotos.current, prepared]
            currentPhotos.current = next
            currentOnChange.current(next)
          }
        } catch (failure) {
          if (active.current && !(failure instanceof Error && failure.name === 'AbortError'))
            setError(t`Не удалось подготовить фотографию. Выберите её ещё раз.`)
        } finally {
          controllers.current.delete(file)
          if (active.current) setPending((items) => items.filter((item) => item !== file))
        }
      }
    } finally {
      if (active.current) {
        setPending([])
        onPreparingChange?.(false)
      }
    }
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 empty:hidden">
        {pending.map((file, index) => (
          <div className="relative" key={`${file.name}-${index}`}>
            <QuestionPhotoPreview photo={file} />
            <span
              role="status"
              className="text-caption text-muted-foreground"
            >{t`Готовим фото…`}</span>
            <Button
              type="button"
              variant="secondary"
              size="icon-sm"
              aria-label={t`Отменить подготовку фотографии ${index + 1}`}
              onClick={() => {
                controllers.current.get(file)?.abort()
                setPending((items) => items.filter((item) => item !== file))
              }}
            >
              <X aria-hidden="true" />
            </Button>
          </div>
        ))}
        {photos.map((photo, index) => (
          <div className="relative" key={index}>
            <QuestionPhotoPreview photo={photo} />
            <Button
              type="button"
              variant="secondary"
              size="icon-sm"
              className="absolute right-0 top-0"
              disabled={disabled || pending.length > 0}
              aria-label={t`Убрать фотографию ${index + 1}`}
              onClick={() => {
                setError('')
                onChange(
                  photos.filter((_, i) => i !== index),
                  index,
                )
              }}
            >
              <X aria-hidden="true" />
            </Button>
          </div>
        ))}
      </div>
      <input
        hidden
        ref={gallery}
        aria-label={t`Выбрать фотографии`}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
        multiple
        disabled={disabled || pending.length > 0}
        onChange={(event) => void select(event.currentTarget)}
      />
      <input
        hidden
        ref={camera}
        aria-label={t`Сделать фотографию`}
        type="file"
        accept="image/*"
        capture="environment"
        disabled={disabled || pending.length > 0}
        onChange={(event) => void select(event.currentTarget)}
      />
      <div className="grid grid-cols-[auto_auto_minmax(0,1fr)] items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="icon"
          disabled={disabled || photos.length >= 10}
          aria-label={t`Выбрать фотографии`}
          title={t`Выбрать фотографии`}
          onClick={() => gallery.current?.click()}
        >
          <ImagePlus aria-hidden="true" />
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="icon"
          disabled={disabled || photos.length >= 10}
          aria-label={t`Сделать фотографию`}
          title={t`Сделать фотографию`}
          onClick={() => camera.current?.click()}
        >
          <Camera aria-hidden="true" />
        </Button>
        <div className="flex min-w-0 justify-end">{action}</div>
      </div>
      {error ? (
        <p role="alert" className="text-small text-danger">
          {error}
        </p>
      ) : null}
    </div>
  )
}
function QuestionPhotoPreview({ photo }: { photo: Blob }) {
  const ref = useRef<HTMLImageElement>(null)
  useEffect(() => {
    const url = URL.createObjectURL(photo)
    if (ref.current) ref.current.src = url
    return () => URL.revokeObjectURL(url)
  }, [photo])
  return <img ref={ref} alt={t`Выбранная фотография`} className="size-20 rounded object-cover" />
}

export function SupportPhotoBody({
  text,
  photoIds,
  audience,
}: {
  text: string | null
  photoIds: string[]
  audience: 'student' | 'staff'
}) {
  return (
    <div className="space-y-2">
      <div className="whitespace-pre-wrap">{text}</div>
      {photoIds.map((id, index) => (
        <ZoomableFigure key={id} alt={t`Фотография ${index + 1}`}>
          <img
            loading="lazy"
            className="max-h-96 max-w-full object-contain"
            src={`/${audience}/api/v1/questions/photos/${encodeURIComponent(id)}`}
            alt={t`Фотография ${index + 1}`}
          />
        </ZoomableFigure>
      ))}
    </div>
  )
}
