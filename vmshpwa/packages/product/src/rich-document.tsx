import katex from 'katex'
import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'

import type { RichBlock, RichDocument, RichInline } from '@vmsh/contracts'
import { cn } from '@vmsh/ui'

import 'katex/dist/katex.min.css'

/** Safe React renderer for the RichDocument v1 contract from Phase 8. */
function MathFormula({ block = false, latex }: { block?: boolean; latex: string }) {
  const element = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!element.current) return
    try {
      katex.render(latex, element.current, {
        displayMode: block,
        throwOnError: false,
        trust: false,
      })
    } catch {
      element.current.textContent = latex
    }
  }, [block, latex])
  return <span className={cn(block && 'block overflow-x-auto py-2 text-center')} ref={element} />
}

function Inline({ nodes }: { nodes: RichInline[] }) {
  const [revealed, setRevealed] = useState<ReadonlySet<number>>(() => new Set())
  const render = (node: RichInline, path: string): ReactNode => {
    if (node.type === 'text') return <Fragment key={path}>{node.text}</Fragment>
    if (node.type === 'code')
      return (
        <code className="rounded bg-surface-sunken px-1 font-mono text-[0.9em]" key={path}>
          {node.text}
        </code>
      )
    if (node.type === 'math') return <MathFormula key={path} latex={node.latex} />
    if (node.type === 'footnoteRef')
      return (
        <sup key={path}>
          <a className="text-link underline" href={`#footnote-${node.id}`}>
            [{node.id}]
          </a>
        </sup>
      )
    if (node.type === 'link') {
      return (
        <a
          className="text-link underline underline-offset-2"
          href={node.href}
          key={path}
          rel="noopener noreferrer"
          target="_blank"
        >
          <Inline nodes={node.children} />
        </a>
      )
    }
    const children = <Inline nodes={node.children} />
    if (node.type === 'bold') return <strong key={path}>{children}</strong>
    if (node.type === 'italic') return <em key={path}>{children}</em>
    if (node.type === 'underline') return <u key={path}>{children}</u>
    if (node.type === 'strike') return <s key={path}>{children}</s>
    if (node.type === 'mark')
      return (
        <mark className="bg-status-warning-surface text-foreground" key={path}>
          {children}
        </mark>
      )
    if (node.type === 'sub') return <sub key={path}>{children}</sub>
    if (node.type === 'sup') return <sup key={path}>{children}</sup>
    return revealed.has(Number(path.split('-').at(-1))) ? (
      <span key={path}>{children}</span>
    ) : (
      <button
        aria-label="Показать скрытый текст"
        className="select-none rounded bg-surface-sunken px-1 blur-[4px] transition-[filter] hover:blur-none focus-visible:blur-none"
        key={path}
        onClick={() =>
          setRevealed((previous) => new Set(previous).add(Number(path.split('-').at(-1))))
        }
        type="button"
      >
        {children}
      </button>
    )
  }
  return <>{nodes.map((node, index) => render(node, `inline-${index}`))}</>
}

function ImageBlock({
  block,
  document,
}: {
  block: Extract<RichBlock, { type: 'image' }>
  document: RichDocument
}) {
  const media = document.media.find((item) => item.mediaId === block.mediaId)
  if (!media?.url) {
    return (
      <div
        aria-label="Картинка будет скопирована при сохранении"
        className="rounded-md border border-dashed border-border p-4 text-caption text-muted-foreground"
        role="status"
      >
        Картинка будет скопирована при сохранении
      </div>
    )
  }
  return (
    <img
      alt={block.alt || media.alt}
      className="max-h-[32rem] rounded-md border border-border object-contain"
      height={media.height}
      loading="lazy"
      src={media.url}
      width={media.width}
    />
  )
}

function Block({ block, document }: { block: RichBlock; document: RichDocument }): ReactNode {
  if (block.type === 'paragraph')
    return (
      <p className="whitespace-pre-wrap">
        <Inline nodes={block.children} />
      </p>
    )
  if (block.type === 'heading') {
    const Heading = `h${block.level}` as 'h1'
    const size = ['text-title', 'text-subtitle', 'text-label', 'text-label', 'text-small'][
      block.level - 1
    ]
    return (
      <Heading className={cn('font-semibold text-foreground', size)}>
        <Inline nodes={block.children} />
      </Heading>
    )
  }
  if (block.type === 'quote')
    return (
      <blockquote className="space-y-2 border-l-2 border-border-strong pl-3 text-muted-foreground">
        {block.blocks.map((item, index) => (
          <Fragment key={index}>
            <Block block={item} document={document} />
          </Fragment>
        ))}
      </blockquote>
    )
  if (block.type === 'divider') return <hr className="border-border" />
  if (block.type === 'code')
    return (
      <pre className="overflow-x-auto rounded-md bg-surface-sunken p-3 font-mono text-caption">
        <code data-language={block.language}>{block.code}</code>
      </pre>
    )
  if (block.type === 'math') return <MathFormula block latex={block.latex} />
  if (block.type === 'list') {
    const List = block.ordered ? 'ol' : 'ul'
    return (
      <List
        className={cn('space-y-1 pl-5', block.ordered ? 'list-decimal' : 'list-disc')}
        start={block.ordered ? block.start : undefined}
      >
        {block.items.map((item, index) => (
          <li key={index}>
            <Inline nodes={item} />
          </li>
        ))}
      </List>
    )
  }
  if (block.type === 'taskList')
    return (
      <ul className="space-y-1 pl-0">
        {block.items.map((item, index) => (
          <li className="flex gap-2" key={index}>
            <span
              aria-label={item.checked ? 'Выполнено' : 'Не выполнено'}
              aria-checked={item.checked}
              role="checkbox"
            >
              {item.checked ? '☑' : '☐'}
            </span>
            <Inline nodes={item.children} />
          </li>
        ))}
      </ul>
    )
  if (block.type === 'details')
    return (
      <details className="rounded-md border border-border bg-surface-subtle p-2" open={block.open}>
        <summary className="cursor-pointer font-medium">
          <Inline nodes={block.summary} />
        </summary>
        <div className="mt-2 space-y-2">
          {block.blocks.map((item, index) => (
            <Fragment key={index}>
              <Block block={item} document={document} />
            </Fragment>
          ))}
        </div>
      </details>
    )
  if (block.type === 'footnote')
    return (
      <p className="text-caption text-muted-foreground" id={`footnote-${block.id}`}>
        <sup>[{block.id}]</sup> <Inline nodes={block.children} />
      </p>
    )
  return <ImageBlock block={block} document={document} />
}

export function RichDocumentView({
  className,
  document,
}: {
  className?: string
  document: RichDocument
}) {
  return (
    <article className={cn('space-y-3', className)}>
      {document.blocks.map((block, index) => (
        <Fragment key={index}>
          <Block block={block} document={document} />
        </Fragment>
      ))}
    </article>
  )
}
