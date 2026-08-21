import { RichParseError, parseMarkdown } from '@puregram/rich'
import {
  isRichHttpsUrl,
  richDocumentSchema,
  type RichBlock,
  type RichDocument,
  type RichInline,
  type RichMedia,
} from '@vmsh/contracts'

/** Strict authoring adapter for the Phase-8 RichDocument v1 subset. */
export class RichMarkdownDiagnostic extends Error {
  readonly from: number
  readonly to: number

  constructor(message: string, from = 0, to = from + 1) {
    super(message)
    this.name = 'RichMarkdownDiagnostic'
    this.from = from
    this.to = to
  }
}

type NativeNode = string | NativeNode[] | { type: string; [key: string]: unknown }

function record(value: unknown): { type: string; [key: string]: unknown } {
  if (
    !value ||
    typeof value !== 'object' ||
    Array.isArray(value) ||
    typeof (value as { type?: unknown }).type !== 'string'
  ) {
    throw new RichMarkdownDiagnostic('Некорректный узел rich Markdown')
  }
  return value as { type: string; [key: string]: unknown }
}

function object(value: unknown, message: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new RichMarkdownDiagnostic(message)
  }
  return value as Record<string, unknown>
}

function array(value: unknown, message: string): NativeNode[] {
  if (!Array.isArray(value)) throw new RichMarkdownDiagnostic(message)
  return value as NativeNode[]
}

function sourcePosition(source: string, needle: string): number {
  const index = source.indexOf(needle)
  return index >= 0 ? index : 0
}

function inline(value: NativeNode, source: string): RichInline[] {
  if (typeof value === 'string') return value ? [{ type: 'text', text: value }] : []
  if (Array.isArray(value)) return value.flatMap((item) => inline(item, source))
  const node = record(value)
  if (node.type === 'mathematical_expression') {
    if (typeof node.expression !== 'string' || !node.expression.trim()) {
      throw new RichMarkdownDiagnostic('Формула не должна быть пустой')
    }
    return [{ type: 'math', latex: node.expression }]
  }
  if (node.type === 'reference_link') {
    if (typeof node.reference_name !== 'string')
      throw new RichMarkdownDiagnostic('Некорректная сноска')
    return [{ type: 'footnoteRef', id: node.reference_name }]
  }
  if (node.type === 'url') {
    if (typeof node.url !== 'string' || !isRichHttpsUrl(node.url)) {
      throw new RichMarkdownDiagnostic(
        'Ссылка должна быть безопасным HTTPS URL',
        sourcePosition(source, typeof node.url === 'string' ? node.url : ''),
      )
    }
    return [{ type: 'link', href: node.url, children: inline(node.text as NativeNode, source) }]
  }
  const wrapped = new Map<string, RichInline['type']>([
    ['bold', 'bold'],
    ['italic', 'italic'],
    ['underline', 'underline'],
    ['strikethrough', 'strike'],
    ['marked', 'mark'],
    ['spoiler', 'spoiler'],
    ['subscript', 'sub'],
    ['superscript', 'sup'],
  ])
  const outputType = wrapped.get(node.type)
  if (outputType) {
    return [
      {
        type: outputType as Exclude<
          RichInline['type'],
          'text' | 'code' | 'link' | 'math' | 'footnoteRef'
        >,
        children: inline(node.text as NativeNode, source),
      },
    ]
  }
  if (node.type === 'code') {
    if (typeof node.text !== 'string') throw new RichMarkdownDiagnostic('Некорректный inline code')
    return [{ type: 'code', text: node.text }]
  }
  throw new RichMarkdownDiagnostic(
    `Синтаксис «${node.type}» пока не поддерживается`,
    sourcePosition(source, `<${node.type}`),
  )
}

function singleInlineBlock(value: unknown, source: string): RichInline[] {
  const blocks = array(value, 'Некорректный элемент списка')
  if (blocks.length !== 1 || record(blocks[0]).type !== 'paragraph') {
    throw new RichMarkdownDiagnostic('Вложенные списки пока не поддерживаются')
  }
  return inline(record(blocks[0]).text as NativeNode, source)
}

function block(value: unknown, source: string, media: RichMedia[]): RichBlock {
  const node = record(value)
  if (node.type === 'paragraph') {
    const text = node.text as NativeNode
    const reference =
      typeof text === 'object' && text !== null && !Array.isArray(text) ? record(text) : null
    if (reference?.type === 'reference') {
      if (typeof reference.name !== 'string')
        throw new RichMarkdownDiagnostic('Некорректная сноска')
      return {
        type: 'footnote',
        id: reference.name,
        children: inline(reference.text as NativeNode, source),
      }
    }
    return { type: 'paragraph', children: inline(text, source) }
  }
  if (node.type === 'heading') {
    if (typeof node.size !== 'number' || node.size < 1 || node.size > 5) {
      throw new RichMarkdownDiagnostic(
        'Заголовок уровня 6 не поддерживается',
        sourcePosition(source, '######'),
      )
    }
    return {
      type: 'heading',
      level: node.size as 1 | 2 | 3 | 4 | 5,
      children: inline(node.text as NativeNode, source),
    }
  }
  if (node.type === 'blockquote') {
    return {
      type: 'quote',
      blocks: array(node.blocks, 'Некорректная цитата').map((item) => block(item, source, media)),
    }
  }
  if (node.type === 'divider') return { type: 'divider' }
  if (node.type === 'pre') {
    if (typeof node.text !== 'string') throw new RichMarkdownDiagnostic('Некорректный блок кода')
    return {
      type: 'code',
      code: node.text,
      ...(typeof node.language === 'string' && node.language ? { language: node.language } : {}),
    }
  }
  if (node.type === 'mathematical_expression') {
    if (typeof node.expression !== 'string' || !node.expression.trim())
      throw new RichMarkdownDiagnostic('Формула не должна быть пустой')
    return { type: 'math', latex: node.expression }
  }
  if (node.type === 'list') {
    const items = array(node.items, 'Некорректный список').map((item) =>
      object(item, 'Некорректный элемент списка'),
    )
    const hasCheckbox = items.some((item) => item.has_checkbox === true)
    if (hasCheckbox && !items.every((item) => item.has_checkbox === true)) {
      throw new RichMarkdownDiagnostic('Нельзя смешивать обычные пункты и задачи в одном списке')
    }
    if (hasCheckbox) {
      return {
        type: 'taskList',
        items: items.map((item) => ({
          checked: item.is_checked === true,
          children: singleInlineBlock(item.blocks, source),
        })),
      }
    }
    const ordered = items.some((item) => typeof item.value === 'number')
    if (ordered && !items.every((item) => typeof item.value === 'number'))
      throw new RichMarkdownDiagnostic('Некорректный упорядоченный список')
    return {
      type: 'list',
      ordered,
      ...(ordered ? { start: Number(items[0]?.value ?? 1) } : {}),
      items: items.map((item) => singleInlineBlock(item.blocks, source)),
    }
  }
  if (node.type === 'details') {
    return {
      type: 'details',
      summary: inline(node.summary as NativeNode, source),
      open: node.is_open === true,
      blocks: array(node.blocks, 'Некорректный details').map((item) => block(item, source, media)),
    }
  }
  // `@puregram/rich` represents Markdown GIFs as a video node. It is still an
  // image in our subset, while all other video/audio syntax remains rejected.
  const gifVideo =
    node.type === 'video' &&
    typeof record(node.video).media === 'string' &&
    /\.gif(?:$|[?#])/iu.test(String(record(node.video).media))
  if (node.type === 'photo' || node.type === 'animation' || gifVideo) {
    const mediaNode = record(node[node.type === 'video' ? 'video' : node.type])
    if (typeof mediaNode.media !== 'string' || !isRichHttpsUrl(mediaNode.media)) {
      throw new RichMarkdownDiagnostic('Картинка должна быть отдельным HTTPS URL')
    }
    const mediaId = `media-${media.length + 1}`
    media.push({
      mediaId,
      sourceUrl: mediaNode.media,
      alt: '',
      mimeType:
        node.type === 'animation' || /\.gif(?:$|[?#])/iu.test(mediaNode.media)
          ? 'image/gif'
          : 'image/webp',
      width: 1,
      height: 1,
    })
    return { type: 'image', mediaId, alt: '' }
  }
  if (node.type === 'table')
    throw new RichMarkdownDiagnostic('Таблицы пока не поддерживаются', sourcePosition(source, '|'))
  if (['video', 'audio', 'voice_note'].includes(node.type))
    throw new RichMarkdownDiagnostic('Видео и аудио пока не поддерживаются')
  throw new RichMarkdownDiagnostic(`Блок «${node.type}» пока не поддерживается`)
}

function rejectNestedLists(source: string): void {
  const nested = /^\s{2,}(?:[-*+]\s+|\d+\.\s+)/mu.exec(source)
  if (nested?.index !== undefined)
    throw new RichMarkdownDiagnostic(
      'Вложенные списки пока не поддерживаются',
      nested.index,
      nested.index + nested[0].length,
    )
}

function rejectUnclosedInlineMath(source: string): void {
  const delimiters: number[] = []
  for (let index = 0; index < source.length; index += 1) {
    if (source[index] === '\\') {
      index += 1
      continue
    }
    if (source[index] !== '$') continue
    if (source[index + 1] === '$') {
      index += 1
      continue
    }
    delimiters.push(index)
  }
  if (delimiters.length % 2 === 1) {
    const from = delimiters.at(-1) ?? 0
    throw new RichMarkdownDiagnostic('Незакрытая inline-формула', from, from + 1)
  }
}

/** Parse Markdown with @puregram/rich and narrow it to the supported PWA subset. */
export function parseRichMarkdown(markdown: string): RichDocument {
  if (!markdown.trim()) throw new RichMarkdownDiagnostic('Введите текст публикации')
  rejectNestedLists(markdown)
  rejectUnclosedInlineMath(markdown)
  try {
    const media: RichMedia[] = []
    const parsed = parseMarkdown(markdown) as unknown[]
    const document = {
      schemaVersion: 1 as const,
      blocks: parsed.map((item) => block(item, markdown, media)),
      media,
    }
    return richDocumentSchema.parse(document)
  } catch (error) {
    if (error instanceof RichMarkdownDiagnostic) throw error
    if (error instanceof RichParseError) {
      throw new RichMarkdownDiagnostic(error.message, error.position, error.position + 1)
    }
    throw error
  }
}

export function richDocumentPlainText(document: RichDocument): string {
  const inlineText = (nodes: RichInline[]): string =>
    nodes
      .map((node) =>
        'text' in node
          ? node.text
          : 'children' in node
            ? inlineText(node.children)
            : node.type === 'math'
              ? node.latex
              : node.type === 'footnoteRef'
                ? `[^${node.id}]`
                : '',
      )
      .join('')
  const blockText = (blocks: RichBlock[]): string =>
    blocks
      .map((item) => {
        if (item.type === 'paragraph' || item.type === 'heading' || item.type === 'footnote')
          return inlineText(item.children)
        if (item.type === 'quote') return blockText(item.blocks)
        if (item.type === 'details') return `${inlineText(item.summary)} ${blockText(item.blocks)}`
        if (item.type === 'list') return item.items.map(inlineText).join('\n')
        if (item.type === 'taskList')
          return item.items.map((entry) => inlineText(entry.children)).join('\n')
        if (item.type === 'code') return item.code
        if (item.type === 'math') return item.latex
        if (item.type === 'image') return item.alt || '[Картинка]'
        return ''
      })
      .filter(Boolean)
      .join('\n')
  return blockText(document.blocks)
}
