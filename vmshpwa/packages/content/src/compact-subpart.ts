import katex from 'katex'

import type { WebContentBlock, WebInlineNode } from '@vmsh/contracts'

import { katexRenderOptions } from './katex-rendering'

const simpleMathElements = new Set([
  'mrow',
  'mi',
  'mn',
  'mo',
  'mtext',
  'mspace',
  'msup',
  'msub',
  'msubsup',
])

function simpleMathText(latex: string): string | null {
  if (typeof document === 'undefined') return null
  const container = document.createElement('span')
  try {
    katex.render(latex, container, { ...katexRenderOptions, output: 'mathml' })
  } catch {
    return null
  }
  const expression = container.querySelector('semantics')?.firstElementChild
  if (!expression || !simpleMathElements.has(expression.localName)) return null
  for (const element of expression.querySelectorAll('*')) {
    if (!simpleMathElements.has(element.localName)) return null
  }
  return expression.textContent
}

function visibleText(nodes: WebInlineNode[]): string | null {
  let text = ''
  for (const node of nodes) {
    let value: string | null
    if (node.type === 'text' || node.type === 'code') {
      // The compiler emits explicit TeX breaks as individual newline tokens.
      if (node.value === '\n' || (node.type === 'code' && /[\r\n]/u.test(node.value))) return null
      value = node.value
    } else if (node.type === 'math') {
      value = simpleMathText(node.latex)
    } else {
      value = visibleText(node.children)
    }
    if (value === null) return null
    text += value
  }
  return text
}

// docs/task-titles.md: measure the displayed paragraph, including punctuation.
export function compactSubpart(blocks: WebContentBlock[]): WebInlineNode[] | null {
  const [paragraph] = blocks
  if (blocks.length !== 1 || paragraph?.type !== 'paragraph') return null
  const text = visibleText(paragraph.children)
  if (text === null) return null
  const length = Array.from(text.trim().replace(/[ \t\r\n]+/gu, ' ')).length
  return length > 0 && length < 20 ? paragraph.children : null
}
