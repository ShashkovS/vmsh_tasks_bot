import renderMathInElement from 'katex/contrib/auto-render'
import { useEffect, useRef } from 'react'

import { katexRenderOptions } from './katex-rendering'
import { sanitizeSemanticHtml } from './sanitizer'

import './content.css'

export { katexRenderLimits, katexRenderOptions, MathExpression } from './katex-rendering'
export { usePublishedContentReplacement } from './content-update'
export { MathDocument, SemanticMathDocument } from './math-document'
export {
  ContentNetworkError,
  ContentProtocolError,
  createContentApiClient,
  useContentDiagnosticsQuery,
  useContentPreviewQuery,
  usePublishedContentQuery,
  useStaffContentHistoryQuery,
} from './content-client'
export type {
  ContentApiClient,
  ContentApiClientOptions,
  ContentRequestOptions,
  PublicationSlotVersion,
  PublishedContentInput,
  PublishContentInput,
  UploadContentSourceInput,
  VersionedContentResource,
} from './content-client'
export { sanitizeSemanticHtml, semanticHtmlTags } from './sanitizer'
export { ZoomableAssetFigure } from './zoomable-asset-figure'
export type { MathExpressionProps } from './katex-rendering'
export type { MathDocumentProps, SemanticMathDocumentProps } from './math-document'
export type { SemanticHtmlSanitizationResult } from './sanitizer'
export type { ZoomableAssetFigureProps } from './zoomable-asset-figure'

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

/**
 * Compatibility renderer for the safe legacy HTML derivative. New API data
 * uses `SemanticMathDocument` and the Zod `WebContentDocument` boundary.
 */
export function MathHtml({ html, className }: MathHtmlProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const fallbackRef = useRef<HTMLDivElement>(null)
  const formulaWarningRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    const fallback = fallbackRef.current
    const formulaWarning = formulaWarningRef.current
    if (!container || !fallback || !formulaWarning) return
    const result = sanitizeSemanticHtml(html)
    if (!result.ok) {
      container.replaceChildren()
      fallback.hidden = false
      formulaWarning.hidden = true
      return
    }

    fallback.hidden = true
    formulaWarning.hidden = true
    container.replaceChildren(result.fragment)

    // Wide tables get a local horizontal scroll so a formula-heavy row never
    // clips or forces the whole page to scroll sideways.
    container.querySelectorAll('table').forEach((table) => {
      if (table.parentElement?.classList.contains('vmsh-scroll-x')) return
      const scroller = document.createElement('div')
      scroller.className = 'vmsh-scroll-x'
      scroller.setAttribute('aria-label', 'Таблица с горизонтальной прокруткой')
      scroller.setAttribute('role', 'region')
      scroller.tabIndex = 0
      table.replaceWith(scroller)
      scroller.append(table)
    })

    let formulaErrors = 0
    renderMathInElement(container, {
      ...katexRenderOptions,
      delimiters: mathDelimiters,
      errorCallback: () => {
        formulaErrors += 1
      },
    })
    formulaWarning.hidden = formulaErrors === 0
  }, [html])

  return (
    <div
      className={['vmsh-math-content font-reading leading-8', className].filter(Boolean).join(' ')}
    >
      <div className="vmsh-content-fallback" hidden ref={fallbackRef} role="alert">
        Материал не показан: его безопасный формат не прошёл проверку.
      </div>
      <div className="vmsh-content-formula-warning" hidden ref={formulaWarningRef} role="status">
        Некоторые формулы не удалось отобразить. Их исходная запись оставлена в тексте.
      </div>
      <div ref={containerRef} />
    </div>
  )
}

export interface ContentArtifact {
  source: 'latex'
  sourceVersion: string
  html: string
  assetIds: string[]
  generatedAt: string
}
