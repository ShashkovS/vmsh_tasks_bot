import { defaultKeymap } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { linter, type Diagnostic } from '@codemirror/lint'
import { EditorState } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import type { BlockContext, InlineContext, Line, MarkdownConfig } from '@lezer/markdown'
import { EditorView } from '@codemirror/view'
import type { RichDocument } from '@vmsh/contracts'
import { RichDocumentView, RichMarkdownDiagnostic, parseRichMarkdown } from '@vmsh/product'
import { useEffect, useMemo, useRef } from 'react'

/**
 * Phase-8 Rich Markdown v1 authoring surface. Custom Lezer nodes deliberately
 * cover only the supported Telegram additions; strict @puregram/rich remains
 * the authoritative parser and produces the diagnostics shown by the linter.
 */
const telegramMarkdown: MarkdownConfig = {
  defineNodes: [
    'TelegramMarked',
    'TelegramSpoiler',
    'TelegramInlineMath',
    { name: 'TelegramMathBlock', block: true },
    { name: 'TelegramFootnote', block: true },
    { name: 'TelegramMedia', block: true },
    { name: 'TelegramDetails', block: true },
  ],
  parseInline: [
    {
      name: 'TelegramMarked',
      before: 'Emphasis',
      parse(cx: InlineContext, next: number, pos: number) {
        if (next !== 61 || cx.slice(pos, pos + 2) !== '==') return -1
        const tail = cx.slice(pos + 2, cx.end)
        const close = tail.indexOf('==')
        const end = close < 0 ? -1 : pos + 2 + close
        if (end < 0) return -1
        cx.addElement(cx.elt('TelegramMarked', pos, end + 2))
        return end + 2
      },
    },
    {
      name: 'TelegramSpoiler',
      before: 'Emphasis',
      parse(cx: InlineContext, next: number, pos: number) {
        if (next !== 124 || cx.slice(pos, pos + 2) !== '||') return -1
        const tail = cx.slice(pos + 2, cx.end)
        const close = tail.indexOf('||')
        const end = close < 0 ? -1 : pos + 2 + close
        if (end < 0) return -1
        cx.addElement(cx.elt('TelegramSpoiler', pos, end + 2))
        return end + 2
      },
    },
    {
      name: 'TelegramInlineMath',
      before: 'Emphasis',
      parse(cx: InlineContext, next: number, pos: number) {
        if (next !== 36 || cx.slice(pos, pos + 2) === '$$') return -1
        const tail = cx.slice(pos + 1, cx.end)
        const close = tail.indexOf('$')
        const end = close < 0 ? -1 : pos + 1 + close
        if (end <= pos + 1) return -1
        cx.addElement(cx.elt('TelegramInlineMath', pos, end + 1))
        return end + 1
      },
    },
  ],
  parseBlock: [
    {
      name: 'TelegramMathBlock',
      before: 'FencedCode',
      parse(cx: BlockContext, line: Line) {
        if (!line.text.startsWith('$$')) return false
        const start = cx.lineStart
        const end = start + line.text.length
        if (line.text.trimEnd().endsWith('$$') && line.text.trim() !== '$$') {
          cx.nextLine()
          cx.addElement(cx.elt('TelegramMathBlock', start, end))
          return true
        }
        return false
      },
    },
    {
      name: 'TelegramFootnote',
      before: 'LinkReference',
      parse(cx: BlockContext, line: Line) {
        if (!/^\[\^[^\]\s]+\]:\s+.+/u.test(line.text)) return false
        cx.nextLine()
        cx.addElement(cx.elt('TelegramFootnote', cx.lineStart, cx.lineStart + line.text.length))
        return true
      },
    },
    {
      name: 'TelegramMedia',
      before: 'FencedCode',
      parse(cx: BlockContext, line: Line) {
        if (!/^!\[[^\]]*\]\(https:\/\/[^\s)]+\)\s*$/u.test(line.text)) return false
        const start = cx.lineStart
        cx.nextLine()
        cx.addElement(cx.elt('TelegramMedia', start, start + line.text.length))
        return true
      },
    },
    {
      name: 'TelegramDetails',
      before: 'HTMLBlock',
      parse(cx: BlockContext, line: Line) {
        if (!/^<details(?:\s|>)/iu.test(line.text)) return false
        const start = cx.lineStart
        cx.nextLine()
        cx.addElement(cx.elt('TelegramDetails', start, start + line.text.length))
        return true
      },
    },
  ],
}

function diagnostic(markdown: string): Diagnostic[] {
  try {
    parseRichMarkdown(markdown)
    return []
  } catch (error) {
    if (error instanceof RichMarkdownDiagnostic) {
      return [
        {
          from: error.from,
          to: Math.max(error.from + 1, error.to),
          severity: 'error',
          message: error.message,
        },
      ]
    }
    return [
      {
        from: 0,
        to: Math.max(1, markdown.length),
        severity: 'error',
        message: 'Не удалось проверить Markdown',
      },
    ]
  }
}

function Editor({
  id,
  onChange,
  value,
}: {
  id?: string
  onChange: (value: string) => void
  value: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const initialId = useRef(id)
  const initialValue = useRef(value)
  const onChangeRef = useRef(onChange)

  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  useEffect(() => {
    if (!host.current) return
    const state = EditorState.create({
      doc: initialValue.current,
      extensions: [
        keymap.of(defaultKeymap),
        markdown({ extensions: [telegramMarkdown] }),
        linter((current) => diagnostic(current.state.doc.toString()), { delay: 150 }),
        EditorView.lineWrapping,
        EditorView.contentAttributes.of({
          ...(initialId.current === undefined ? {} : { id: initialId.current }),
          'aria-label': 'Markdown публикации',
        }),
        EditorView.theme({
          '&': {
            border: '1px solid var(--color-border)',
            borderRadius: '0.375rem',
            minHeight: '22rem',
            textAlign: 'left',
          },
          '&.cm-focused': { outline: '2px solid var(--color-ring)', outlineOffset: '2px' },
          '.cm-scroller': { fontFamily: 'var(--font-mono)', fontSize: '0.875rem' },
          '.cm-content': { padding: '0.75rem' },
        }),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) onChangeRef.current(update.state.doc.toString())
        }),
      ],
    })
    view.current = new EditorView({ state, parent: host.current })
    return () => {
      view.current?.destroy()
      view.current = null
    }
  }, [])

  useEffect(() => {
    const current = view.current
    if (current && value !== current.state.doc.toString()) {
      current.dispatch({ changes: { from: 0, to: current.state.doc.length, insert: value } })
    }
  }, [value])

  return <div ref={host} />
}

export function RichMarkdownEditor({
  id,
  onChange,
  onDocumentChange,
  value,
}: {
  id?: string
  onChange: (value: string) => void
  onDocumentChange?: (document: RichDocument | null) => void
  value: string
}) {
  const { result, error } = useMemo(() => {
    try {
      return { result: parseRichMarkdown(value), error: null }
    } catch (reason) {
      return {
        result: null,
        error:
          reason instanceof RichMarkdownDiagnostic
            ? reason
            : new RichMarkdownDiagnostic('Не удалось проверить Markdown'),
      }
    }
  }, [value])

  useEffect(() => {
    onDocumentChange?.(result)
  }, [onDocumentChange, result])

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div className="grid gap-1.5">
        <Editor {...(id === undefined ? {} : { id })} onChange={onChange} value={value} />
        {error ? (
          <p className="text-caption text-status-danger" role="alert">
            Строка Markdown не сохранится: {error.message}
          </p>
        ) : (
          <p className="text-caption text-muted-foreground">
            Поддерживаются заголовки h1–h5, списки, формулы, spoilers, сноски, details и отдельные
            HTTPS-картинки.
          </p>
        )}
      </div>
      <section
        aria-label="Предпросмотр Markdown"
        className="min-h-[22rem] rounded-md border border-border bg-surface p-4"
      >
        <p className="mb-3 text-label font-medium">Предпросмотр</p>
        {result ? (
          <RichDocumentView document={result} />
        ) : (
          <p className="text-caption text-muted-foreground">
            Исправьте Markdown, чтобы увидеть предпросмотр.
          </p>
        )}
      </section>
    </div>
  )
}
