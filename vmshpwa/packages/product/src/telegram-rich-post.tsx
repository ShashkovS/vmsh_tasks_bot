import { EyeOff, FileText, Forward, ImageIcon, Play } from 'lucide-react'
import { Fragment, useState, type ReactNode } from 'react'

import { Badge, Button, cn } from '@vmsh/ui'

import {
  toRichTextSegments,
  type TelegramBlock,
  type TelegramEntity,
  type TelegramMedia,
  type TelegramPostState,
  type TelegramPostView,
} from './telegram-post'

function RichText({ text, entities }: { text: string; entities?: TelegramEntity[] | undefined }) {
  const [revealed, setRevealed] = useState<ReadonlySet<number>>(() => new Set())
  const segments = toRichTextSegments(text, entities ?? [])
  return (
    <>
      {segments.map((segment, index) => {
        const entity = segment.entity
        if (!entity) return <Fragment key={index}>{segment.text}</Fragment>
        switch (entity.type) {
          case 'bold':
            return <strong key={index}>{segment.text}</strong>
          case 'italic':
            return <em key={index}>{segment.text}</em>
          case 'underline':
            return <u key={index}>{segment.text}</u>
          case 'strike':
            return <s key={index}>{segment.text}</s>
          case 'code':
            return (
              <code className="rounded bg-surface-sunken px-1 font-mono text-[0.9em]" key={index}>
                {segment.text}
              </code>
            )
          case 'link':
            return (
              <a
                className="text-link underline underline-offset-2"
                href={entity.href}
                key={index}
                rel="noreferrer noopener"
                target="_blank"
              >
                {segment.text}
              </a>
            )
          case 'spoiler':
            return revealed.has(index) ? (
              <span key={index}>{segment.text}</span>
            ) : (
              <button
                aria-label="Показать скрытый текст"
                className="select-none rounded bg-surface-sunken px-1 blur-[4px] transition-[filter] hover:blur-none"
                key={index}
                onClick={() => setRevealed((prev) => new Set(prev).add(index))}
                type="button"
              >
                {segment.text}
              </button>
            )
          case 'mark':
            return (
              <mark className="bg-status-warning-surface text-foreground" key={index}>
                {segment.text}
              </mark>
            )
          case 'sub':
            return <sub key={index}>{segment.text}</sub>
          case 'sup':
            return <sup key={index}>{segment.text}</sup>
        }
      })}
    </>
  )
}

function Block({
  block,
  renderMath,
}: {
  block: TelegramBlock
  renderMath?: ((html: string) => ReactNode) | undefined
}) {
  if (block.kind === 'math') {
    return (
      <div className="my-1">{renderMath ? renderMath(block.html) : <code>{block.html}</code>}</div>
    )
  }
  if (block.kind === 'heading') {
    const sizes = {
      1: 'text-title',
      2: 'text-subtitle',
      3: 'text-label',
      4: 'text-label',
      5: 'text-small',
      6: 'text-small',
    } as const
    const Heading = `h${block.level}` as 'h1'
    return (
      <Heading className={cn('font-semibold text-foreground', sizes[block.level])}>
        <RichText entities={block.entities} text={block.text} />
      </Heading>
    )
  }
  if (block.kind === 'list') {
    const List = block.ordered ? 'ol' : 'ul'
    return (
      <List
        className={cn('space-y-1 pl-5', block.ordered ? 'list-decimal' : 'list-disc')}
        start={block.ordered ? block.start : undefined}
      >
        {block.items.map((item, index) => (
          <li key={index}>
            <RichText entities={item.entities} text={item.text} />
          </li>
        ))}
      </List>
    )
  }
  if (block.kind === 'code') {
    return (
      <pre className="overflow-x-auto rounded-md bg-surface-sunken p-3 font-mono text-caption">
        <code data-language={block.language}>{block.code}</code>
      </pre>
    )
  }
  if (block.kind === 'divider') return <hr className="border-border" />
  if (block.kind === 'table') {
    return (
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-caption">
          {block.caption ? (
            <caption className="pb-1 text-left text-muted-foreground">{block.caption}</caption>
          ) : null}
          {block.headers ? (
            <thead>
              <tr>
                {block.headers.map((header) => (
                  <th
                    className="border border-border bg-surface-subtle px-2 py-1 text-left"
                    key={header}
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
          ) : null}
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <td className="border border-border px-2 py-1" key={cellIndex}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (block.kind === 'details') {
    return (
      <details className="rounded-md border border-border bg-surface-subtle p-2" open={block.open}>
        <summary className="cursor-pointer font-medium">{block.summary}</summary>
        <div className="mt-2 space-y-2">
          {block.blocks.map((nested, index) => (
            <Block block={nested} key={index} renderMath={renderMath} />
          ))}
        </div>
      </details>
    )
  }
  if (block.kind === 'quote') {
    return (
      <blockquote className="border-l-2 border-border-strong pl-3 text-muted-foreground italic">
        <RichText entities={block.entities} text={block.text} />
      </blockquote>
    )
  }
  return (
    <p className="whitespace-pre-wrap">
      <RichText entities={block.entities} text={block.text} />
    </p>
  )
}

function MediaTile({ media }: { media: TelegramMedia }) {
  if (media.kind === 'document') {
    const content = (
      <>
        <FileText aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-small text-foreground">{media.name}</span>
        {media.sizeLabel ? (
          <span className="shrink-0 font-num text-caption text-muted-foreground">
            {media.sizeLabel}
          </span>
        ) : null}
      </>
    )
    return media.url ? (
      <a
        className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 hover:bg-surface-subtle"
        href={media.url}
        rel="noreferrer noopener"
        target="_blank"
      >
        {content}
      </a>
    ) : (
      <div className="flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2">
        {content}
      </div>
    )
  }
  return (
    <div className="relative aspect-video overflow-hidden rounded-md bg-surface-sunken">
      {media.previewUrl ? (
        <img alt={media.alt ?? ''} className="size-full object-cover" src={media.previewUrl} />
      ) : (
        <span className="grid size-full place-items-center text-muted-foreground">
          <ImageIcon aria-hidden="true" className="size-8" />
        </span>
      )}
      {media.kind === 'video' ? (
        <>
          <span className="absolute inset-0 grid place-items-center">
            <Play aria-hidden="true" className="size-8 text-white drop-shadow" />
          </span>
          {media.durationLabel ? (
            <span className="absolute bottom-1 right-1 rounded bg-surface/90 px-1 font-num text-caption text-foreground">
              {media.durationLabel}
            </span>
          ) : null}
        </>
      ) : null}
    </div>
  )
}

function StateNotice({
  state,
  onRetryDelivery,
}: {
  state: TelegramPostState
  onRetryDelivery?: (() => void) | undefined
}) {
  switch (state) {
    case 'source-revised':
      return <Badge variant="info">Изменено в источнике</Badge>
    case 'local-override':
      return <Badge variant="warning">Локальная правка редакции</Badge>
    case 'source-deleted':
      return <Badge variant="neutral">Удалено в источнике</Badge>
    case 'delivery-error':
      return (
        <div className="flex items-center gap-2">
          <Badge variant="danger">Ошибка доставки</Badge>
          {onRetryDelivery ? (
            <Button onClick={onRetryDelivery} size="xs" variant="outline">
              Повторить
            </Button>
          ) : null}
        </div>
      )
    default:
      return null
  }
}

export interface TelegramRichPostProps {
  post: TelegramPostView
  surface?: 'pwa' | 'telegram'
  variant?: 'card' | 'detail'
  renderMath?: (html: string) => ReactNode
  onRetryDelivery?: () => void
  className?: string
  showEditorialState?: boolean
}

export function TelegramRichPost({
  post,
  surface = 'pwa',
  variant = 'detail',
  renderMath,
  onRetryDelivery,
  className,
  showEditorialState = true,
}: TelegramRichPostProps) {
  if (post.state === 'hidden') {
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded-lg border border-dashed border-border bg-surface-subtle p-3 text-small text-muted-foreground',
          className,
        )}
      >
        <EyeOff aria-hidden="true" className="size-4" />
        Пост скрыт редакцией.
      </div>
    )
  }

  const photosAndVideos = (post.media ?? []).filter((media) => media.kind !== 'document')
  const documents = (post.media ?? []).filter((media) => media.kind === 'document')

  return (
    <article
      className={cn(
        'space-y-2 p-4',
        surface === 'telegram'
          ? 'rounded-xl border border-border bg-surface-subtle'
          : 'rounded-lg border border-border bg-surface',
        className,
      )}
    >
      {post.attribution || post.state ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0 space-y-0.5">
            {post.attribution?.forwardedFrom ? (
              <p className="inline-flex items-center gap-1 text-caption text-muted-foreground">
                <Forward aria-hidden="true" className="size-3.5" />
                Переслано из {post.attribution.forwardedFrom}
              </p>
            ) : null}
            {post.attribution?.author || post.attribution?.channel ? (
              <p className="truncate text-label font-medium text-foreground">
                {post.attribution.author ?? post.attribution.channel}
              </p>
            ) : null}
          </div>
          {post.state && showEditorialState ? (
            <StateNotice onRetryDelivery={onRetryDelivery} state={post.state} />
          ) : null}
        </div>
      ) : null}

      <div
        className={cn(
          'space-y-2 text-small leading-relaxed text-foreground',
          variant === 'card' && '[&>p]:line-clamp-3',
          post.state === 'source-deleted' && 'text-muted-foreground line-through',
        )}
      >
        {post.blocks.map((block, index) => (
          <Block block={block} key={index} renderMath={renderMath} />
        ))}
      </div>

      {photosAndVideos.length > 0 ? (
        <div className={cn('grid gap-1', photosAndVideos.length > 1 && 'grid-cols-2')}>
          {photosAndVideos.map((media, index) => (
            <MediaTile key={index} media={media} />
          ))}
        </div>
      ) : null}

      {documents.length > 0 ? (
        <div className="space-y-1">
          {documents.map((media, index) => (
            <MediaTile key={index} media={media} />
          ))}
        </div>
      ) : null}

      {post.at || post.editedAt ? (
        <p className="text-caption text-muted-foreground">
          {post.at}
          {post.editedAt ? ` · изменено ${post.editedAt}` : ''}
        </p>
      ) : null}
    </article>
  )
}
