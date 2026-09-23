import { useState, type ReactNode } from 'react'
import { Play } from 'lucide-react'

import type { LessonRichDocument, LessonVideoBlock, RichBlock } from '@vmsh/contracts'
import { Button, cn } from '@vmsh/ui'

import { RichDocumentView } from './rich-document'
import { lessonVideoEmbedUrl, lessonVideoPrintUrl } from './lesson-video'

import './lesson-blocks.css'

export function LessonVideo({ video }: { video: LessonVideoBlock }) {
  const [loaded, setLoaded] = useState(false)
  const provider = video.provider === 'youtube' ? 'YouTube' : 'VK Видео'
  const label = video.title && video.title !== 'YouTube video player' ? video.title : provider
  const url = lessonVideoPrintUrl(video)
  return (
    <figure className="vmsh-lesson-video" data-print-video>
      {loaded ? (
        <iframe
          allow="accelerometer; autoplay; encrypted-media; fullscreen; picture-in-picture; screen-wake-lock"
          allowFullScreen
          referrerPolicy="strict-origin-when-cross-origin"
          src={lessonVideoEmbedUrl(video)}
          title={label}
        />
      ) : (
        <div className="vmsh-lesson-video-placeholder" data-print-hide>
          <p className="vmsh-lesson-video-title">{label}</p>
          <Button onClick={() => setLoaded(true)} type="button" variant="outline">
            <Play aria-hidden="true" className="size-4" />
            Загрузить видео
          </Button>
        </div>
      )}
      <figcaption className="vmsh-lesson-video-print">
        {label}: <a href={url}>{url}</a>
      </figcaption>
    </figure>
  )
}

export function LessonRichDocumentView({
  className,
  document,
  idPrefix,
}: {
  className?: string
  document: LessonRichDocument
  idPrefix: string
}) {
  const sequence: Array<
    { kind: 'rich'; blocks: RichBlock[] } | { kind: 'video'; video: LessonVideoBlock }
  > = []
  let rich: RichBlock[] = []
  const flush = () => {
    if (rich.length) sequence.push({ kind: 'rich', blocks: rich })
    rich = []
  }
  document.blocks.forEach((block) => {
    if (block.type === 'video') {
      flush()
      sequence.push({ kind: 'video', video: block })
    } else rich.push(block)
  })
  flush()
  return (
    <article className={cn('vmsh-lesson-rich-document', className)}>
      {sequence.map((item, index) =>
        item.kind === 'video' ? (
          <LessonVideo key={`${idPrefix}-video-${index}`} video={item.video} />
        ) : (
          <RichDocumentView
            imageLoading="eager"
            key={`${idPrefix}-rich-${index}`}
            document={{ schemaVersion: 1, blocks: item.blocks, media: document.media }}
            idPrefix={`${idPrefix}-${index}`}
          />
        ),
      )}
    </article>
  )
}

export function LessonBlockView({
  document,
  idPrefix,
}: {
  document: LessonRichDocument
  idPrefix: string
}) {
  return (
    <section className="vmsh-lesson-block">
      <LessonRichDocumentView document={document} idPrefix={idPrefix} />
    </section>
  )
}

export function LessonBlocksLayout({
  before,
  after,
  children,
  idPrefix,
}: {
  before: LessonRichDocument | null
  after: LessonRichDocument | null
  children: ReactNode
  idPrefix: string
}) {
  return (
    <>
      {before ? <LessonBlockView document={before} idPrefix={`${idPrefix}-before`} /> : null}
      {children}
      {after ? <LessonBlockView document={after} idPrefix={`${idPrefix}-after`} /> : null}
    </>
  )
}
