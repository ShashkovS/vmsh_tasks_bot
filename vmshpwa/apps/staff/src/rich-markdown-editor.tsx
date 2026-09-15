import { defaultKeymap } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { linter, type Diagnostic } from '@codemirror/lint'
import { EditorState } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import type { BlockContext, InlineContext, Line, MarkdownConfig } from '@lezer/markdown'
import { EditorView } from '@codemirror/view'
import type { RichDocument } from '@vmsh/contracts'
import { RichDocumentView, RichMarkdownDiagnostic, parseRichMarkdown } from '@vmsh/product'
import { Button } from '@vmsh/ui'
import { ImagePlus } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

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

const previewGracePeriodMs = 2_000

type PreviewState = {
  document: RichDocument | null
  expiresAt: number | null
}

function diagnostic(markdown: string): Diagnostic[] {
  if (!markdown.trim()) return []
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
  onReady,
  value,
}: {
  id?: string
  onChange: (value: string) => void
  onReady?: (insert: (markdown: string) => void) => void
  value: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const initialId = useRef(id)
  const initialValue = useRef(value)
  const onChangeRef = useRef(onChange)
  const onReadyRef = useRef(onReady)

  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])

  useEffect(() => {
    onReadyRef.current = onReady
  }, [onReady])

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
    onReadyRef.current?.((markdown) => {
      const current = view.current
      if (current === null) return
      const selection = current.state.selection.main
      current.dispatch({
        changes: { from: selection.from, to: selection.to, insert: markdown },
        selection: { anchor: selection.from + markdown.length },
      })
      current.focus()
    })
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

function imageAlt(filename: string): string {
  const withoutExtension = filename.replace(/\.[^.]+$/u, '')
  return withoutExtension.replace(/[\[\]]/gu, '').trim() || 'Картинка'
}

export function RichMarkdownEditor({
  id,
  onChange,
  onDocumentChange,
  onImageUpload,
  value,
}: {
  id?: string
  onChange: (value: string) => void
  onDocumentChange?: (document: RichDocument | null) => void
  onImageUpload?: (image: File) => Promise<{ url: string }>
  value: string
}) {
  const isEmpty = value.trim() === ''
  const { result, error } = useMemo(() => {
    if (isEmpty) return { result: null, error: null }
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
  }, [isEmpty, value])
  const [previewState, setPreviewState] = useState<PreviewState>(() => ({
    document: result,
    expiresAt: null,
  }))
  const imageInput = useRef<HTMLInputElement>(null)
  const [insertAtCursor, setInsertAtCursor] = useState<((markdown: string) => void) | null>(null)
  const [imageError, setImageError] = useState<string | null>(null)
  const [isUploadingImage, setIsUploadingImage] = useState(false)

  const handleChange = (markdown: string) => {
    const nextIsEmpty = markdown.trim() === ''
    let nextDocument: RichDocument | null = null
    if (!nextIsEmpty) {
      try {
        nextDocument = parseRichMarkdown(markdown)
      } catch {
        // The strict parser has already reported the diagnostic in the editor.
      }
    }
    setPreviewState((current) => {
      if (nextDocument) return { document: nextDocument, expiresAt: null }
      if (nextIsEmpty) return { document: null, expiresAt: null }
      return {
        document: current.document,
        expiresAt: current.document === null ? null : Date.now() + previewGracePeriodMs,
      }
    })
    onChange(markdown)
  }

  useEffect(() => {
    if (previewState.expiresAt === null) return undefined
    const remaining = Math.max(0, previewState.expiresAt - Date.now())
    const timeout = globalThis.setTimeout(() => {
      setPreviewState((current) =>
        current.expiresAt === previewState.expiresAt
          ? { ...current, document: null, expiresAt: null }
          : current,
      )
    }, remaining)
    return () => globalThis.clearTimeout(timeout)
  }, [previewState.expiresAt])

  const previewDocument = isEmpty ? null : (result ?? previewState.document)

  const uploadImage = async (image: File) => {
    if (!onImageUpload) return
    setImageError(null)
    setIsUploadingImage(true)
    try {
      const uploaded = await onImageUpload(image)
      const markdown = `\n\n![${imageAlt(image.name)}](${uploaded.url})\n`
      if (insertAtCursor) insertAtCursor(markdown)
      else handleChange(`${value}${markdown}`)
    } catch (reason) {
      setImageError(reason instanceof Error ? reason.message : 'Не удалось загрузить картинку.')
    } finally {
      setIsUploadingImage(false)
    }
  }

  useEffect(() => {
    onDocumentChange?.(result)
  }, [onDocumentChange, result])

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div className="grid gap-1.5">
        <Editor
          {...(id === undefined ? {} : { id })}
          onChange={handleChange}
          onReady={(insert) => setInsertAtCursor(() => insert)}
          value={value}
        />
        {onImageUpload ? (
          <div className="flex flex-wrap items-center gap-2">
            <input
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={(event) => {
                const image = event.target.files?.[0]
                event.target.value = ''
                if (image) void uploadImage(image)
              }}
              ref={imageInput}
              type="file"
            />
            <Button
              disabled={isUploadingImage}
              onClick={() => imageInput.current?.click()}
              size="sm"
              type="button"
              variant="outline"
            >
              <ImagePlus aria-hidden="true" />
              {isUploadingImage ? 'Готовим картинку…' : 'Загрузить картинку'}
            </Button>
            <span className="text-caption text-muted-foreground">PNG, JPEG или WebP · до 10 МиБ</span>
          </div>
        ) : null}
        {imageError ? (
          <p className="text-caption text-status-danger" role="alert">
            {imageError}
          </p>
        ) : null}
        {error ? (
          <p className="text-caption text-status-danger" role="alert">
            Исправьте ошибку в markdown.
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
        {previewDocument ? (
          <RichDocumentView document={previewDocument} />
        ) : isEmpty ? (
          <p className="text-caption text-muted-foreground">
            Предпросмотр появится после ввода текста.
          </p>
        ) : (
          <p className="text-caption text-muted-foreground">Исправьте ошибку в markdown.</p>
        )}
      </section>
    </div>
  )
}
