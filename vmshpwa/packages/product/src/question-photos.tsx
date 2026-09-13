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
}: {
  photos: Blob[]
  onChange: (photos: Blob[], removedIndex?: number) => void
  action?: ReactNode
  disabled?: boolean
}) {
  const gallery = useRef<HTMLInputElement>(null)
  const camera = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')
  const select = (input: HTMLInputElement) => {
    const files = Array.from(input.files ?? [])
    input.value = ''
    if (
      files.length + photos.length > 10 ||
      files.some(
        (file) =>
          file.size > 25 * 1024 * 1024 ||
          !['image/jpeg', 'image/png', 'image/webp'].includes(file.type),
      )
    ) {
      setError('Можно прикрепить до 10 фотографий JPEG, PNG или WebP размером до 25 МиБ каждая.')
      return
    }
    setError('')
    onChange([...photos, ...files])
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 empty:hidden">
        {photos.map((photo, index) => (
          <div className="relative" key={index}>
            <QuestionPhotoPreview photo={photo} />
            <Button
              type="button"
              variant="secondary"
              size="icon-sm"
              className="absolute right-0 top-0"
              disabled={disabled}
              aria-label={`Убрать фотографию ${index + 1}`}
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
        aria-label="Выбрать фотографии"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        disabled={disabled}
        onChange={(event) => select(event.currentTarget)}
      />
      <input
        hidden
        ref={camera}
        aria-label="Сделать фотографию"
        type="file"
        accept="image/*"
        capture="environment"
        disabled={disabled}
        onChange={(event) => select(event.currentTarget)}
      />
      <div className="grid grid-cols-[auto_auto_minmax(0,1fr)] items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="icon"
          disabled={disabled || photos.length >= 10}
          aria-label="Выбрать фотографии"
          title="Выбрать фотографии"
          onClick={() => gallery.current?.click()}
        >
          <ImagePlus aria-hidden="true" />
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="icon"
          disabled={disabled || photos.length >= 10}
          aria-label="Сделать фотографию"
          title="Сделать фотографию"
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
  return <img ref={ref} alt="Выбранная фотография" className="size-20 rounded object-cover" />
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
        <ZoomableFigure key={id} alt={`Фотография ${index + 1}`}>
          <img
            loading="lazy"
            className="max-h-96 max-w-full object-contain"
            src={`/${audience}/api/v1/questions/photos/${encodeURIComponent(id)}`}
            alt={`Фотография ${index + 1}`}
          />
        </ZoomableFigure>
      ))}
    </div>
  )
}
