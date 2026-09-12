import katex from 'katex'
import { useEffect, useRef } from 'react'

export const katexRenderLimits = {
  maxExpand: 1_000,
  maxSize: 20,
} as const

export const katexRenderOptions = {
  maxExpand: katexRenderLimits.maxExpand,
  maxSize: katexRenderLimits.maxSize,
  output: 'htmlAndMathml',
  strict: 'warn',
  throwOnError: true,
  trust: false,
} as const

export interface MathExpressionProps {
  latex: string
  display?: boolean
  className?: string
}

/** Client-side KaTeX with bounded expansion/size and a deterministic fallback. */
export function MathExpression({ latex, display = false, className }: MathExpressionProps) {
  const wrapperRef = useRef<HTMLSpanElement>(null)
  const outputRef = useRef<HTMLSpanElement>(null)
  const fallbackRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const wrapper = wrapperRef.current
    const output = outputRef.current
    const fallback = fallbackRef.current
    if (!wrapper || !output || !fallback) return
    output.replaceChildren()
    fallback.hidden = true
    wrapper.dataset.mathState = 'rendered'

    try {
      katex.render(latex, output, { ...katexRenderOptions, displayMode: display })
    } catch {
      output.replaceChildren()
      fallback.hidden = false
      wrapper.dataset.mathState = 'invalid'
    }
  }, [display, latex])

  return (
    <span
      className={[
        'vmsh-math-expression',
        display ? 'vmsh-math-expression-display' : undefined,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      data-math-display={display ? 'true' : 'false'}
      data-math-state="pending"
      ref={wrapperRef}
    >
      <span ref={outputRef} />
      <span className="vmsh-formula-fallback" hidden ref={fallbackRef} role="status">
        Формулу не удалось отобразить: <code>{latex}</code>
      </span>
    </span>
  )
}
