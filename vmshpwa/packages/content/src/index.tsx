import DOMPurify from 'dompurify'
import renderMathInElement from 'katex/contrib/auto-render'
import { useEffect, useRef, type ReactNode } from 'react'

import './content.css'

export interface MathDocumentProps {
  title?: string
  children: ReactNode
  className?: string
}

export function MathDocument({ title, children, className }: MathDocumentProps) {
  return (
    <article className={className} data-slot="math-document">
      {title ? <h1 className="mb-4 font-reading text-2xl font-semibold">{title}</h1> : null}
      <div className="font-reading text-[1.05rem] leading-8">{children}</div>
    </article>
  )
}

export interface MathHtmlProps {
  html: string
  className?: string
}

const mathDelimiters = [
  { left: '$$', right: '$$', display: true },
  { left: '\\[', right: '\\]', display: true },
  { left: '\\(', right: '\\)', display: false },
  { left: '$', right: '$', display: false },
]

/** Renders a sanitized web derivative and applies client-side KaTeX. */
export function MathHtml({ html, className }: MathHtmlProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    container.innerHTML = DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form'],
    })

    // Wide tables get a local horizontal scroll so a formula-heavy row never
    // clips or forces the whole page to scroll sideways.
    container.querySelectorAll('table').forEach((table) => {
      if (table.parentElement?.classList.contains('vmsh-scroll-x')) return
      const scroller = document.createElement('div')
      scroller.className = 'vmsh-scroll-x'
      table.replaceWith(scroller)
      scroller.append(table)
    })

    renderMathInElement(container, {
      delimiters: mathDelimiters,
      output: 'htmlAndMathml',
      strict: 'warn',
      throwOnError: false,
      trust: false,
    })
  }, [html])

  return (
    <div
      ref={containerRef}
      className={['vmsh-math-content font-reading leading-8', className].filter(Boolean).join(' ')}
    />
  )
}

export interface ContentArtifact {
  source: 'latex'
  sourceVersion: string
  html: string
  assetIds: string[]
  generatedAt: string
}
