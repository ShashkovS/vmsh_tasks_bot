import { z } from 'zod'

/**
 * RichDocument v1 is the persisted, renderer-safe representation of Staff-authored
 * Markdown. Its rollout is specified in Phase 8's Rich Markdown v1 increment.
 */
export const richDocumentSchemaVersion = 1 as const

const richTextSchema = z.string().max(32_768)
const richNonEmptyTextSchema = z.string().trim().min(1).max(32_768)
const richIdentifierSchema = z.string().regex(/^[A-Za-z][A-Za-z0-9_.:-]{0,79}$/u)

function hasRichControlCharacter(value: string): boolean {
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0
    if (code <= 31 || code === 127) return true
  }
  return false
}

export function isRichHttpsUrl(value: string): boolean {
  try {
    const url = new URL(value)
    return (
      url.protocol === 'https:' &&
      url.hostname.length > 0 &&
      url.username.length === 0 &&
      url.password.length === 0 &&
      !hasRichControlCharacter(value)
    )
  } catch {
    return false
  }
}

export const richHttpsUrlSchema = z.string().max(4_096).refine(isRichHttpsUrl, {
  message: 'URL must be credential-free HTTPS',
})

export type RichInline =
  | { type: 'text'; text: string }
  | {
      type: 'bold' | 'italic' | 'underline' | 'strike' | 'mark' | 'spoiler'
      children: RichInline[]
    }
  | { type: 'code'; text: string }
  | { type: 'link'; href: string; children: RichInline[] }
  | { type: 'math'; latex: string }
  | { type: 'footnoteRef'; id: string }
  | { type: 'sub' | 'sup'; children: RichInline[] }

export const richInlineSchema: z.ZodType<RichInline> = z.lazy(() =>
  z.discriminatedUnion('type', [
    z.object({ type: z.literal('text'), text: richTextSchema }).strip(),
    z
      .object({
        type: z.enum(['bold', 'italic', 'underline', 'strike', 'mark', 'spoiler', 'sub', 'sup']),
        children: z.array(richInlineSchema).min(1).max(1_000),
      })
      .strip(),
    z.object({ type: z.literal('code'), text: richTextSchema }).strip(),
    z
      .object({
        type: z.literal('link'),
        href: richHttpsUrlSchema,
        children: z.array(richInlineSchema).min(1).max(1_000),
      })
      .strip(),
    z.object({ type: z.literal('math'), latex: richNonEmptyTextSchema }).strip(),
    z.object({ type: z.literal('footnoteRef'), id: richIdentifierSchema }).strip(),
  ]),
)

export type RichBlock =
  | { type: 'paragraph'; children: RichInline[] }
  | { type: 'heading'; level: 1 | 2 | 3 | 4 | 5; children: RichInline[] }
  | { type: 'quote'; blocks: RichBlock[] }
  | { type: 'divider' }
  | { type: 'code'; code: string; language?: string | undefined }
  | { type: 'list'; ordered: boolean; start?: number | undefined; items: RichInline[][] }
  | { type: 'taskList'; items: { checked: boolean; children: RichInline[] }[] }
  | { type: 'details'; summary: RichInline[]; open: boolean; blocks: RichBlock[] }
  | { type: 'math'; latex: string }
  | { type: 'footnote'; id: string; children: RichInline[] }
  | { type: 'image'; mediaId: string; alt: string }

const richTaskItemSchema = z
  .object({ checked: z.boolean(), children: z.array(richInlineSchema).min(1).max(1_000) })
  .strip()

export const richBlockSchema: z.ZodType<RichBlock> = z.lazy(() =>
  z.discriminatedUnion('type', [
    z
      .object({
        type: z.literal('paragraph'),
        children: z.array(richInlineSchema).min(1).max(1_000),
      })
      .strip(),
    z
      .object({
        type: z.literal('heading'),
        level: z.union([z.literal(1), z.literal(2), z.literal(3), z.literal(4), z.literal(5)]),
        children: z.array(richInlineSchema).min(1).max(1_000),
      })
      .strip(),
    z
      .object({ type: z.literal('quote'), blocks: z.array(richBlockSchema).min(1).max(200) })
      .strip(),
    z.object({ type: z.literal('divider') }).strip(),
    z
      .object({
        type: z.literal('code'),
        code: z.string().max(32_768),
        language: z.string().trim().min(1).max(64).optional(),
      })
      .strip(),
    z
      .object({
        type: z.literal('list'),
        ordered: z.boolean(),
        start: z.number().int().min(1).max(10_000).optional(),
        items: z.array(z.array(richInlineSchema).min(1).max(1_000)).min(1).max(200),
      })
      .strip(),
    z
      .object({ type: z.literal('taskList'), items: z.array(richTaskItemSchema).min(1).max(200) })
      .strip(),
    z
      .object({
        type: z.literal('details'),
        summary: z.array(richInlineSchema).min(1).max(1_000),
        open: z.boolean(),
        blocks: z.array(richBlockSchema).min(1).max(200),
      })
      .strip(),
    z.object({ type: z.literal('math'), latex: richNonEmptyTextSchema }).strip(),
    z
      .object({
        type: z.literal('footnote'),
        id: richIdentifierSchema,
        children: z.array(richInlineSchema).min(1).max(1_000),
      })
      .strip(),
    z
      .object({
        type: z.literal('image'),
        mediaId: richIdentifierSchema,
        alt: z.string().max(1_000),
      })
      .strip(),
  ]),
)

export const richMediaSchema = z
  .object({
    mediaId: richIdentifierSchema,
    sourceUrl: richHttpsUrlSchema,
    url: richHttpsUrlSchema.optional(),
    alt: z.string().max(1_000),
    mimeType: z.enum(['image/webp', 'image/gif']),
    width: z.number().int().positive().max(1_920),
    height: z.number().int().positive().max(1_920),
  })
  .strip()
export type RichMedia = z.infer<typeof richMediaSchema>

export const richDocumentSchema = z
  .object({
    schemaVersion: z.literal(richDocumentSchemaVersion),
    blocks: z.array(richBlockSchema).min(1).max(1_000),
    media: z.array(richMediaSchema).max(10),
  })
  .strip()
  .superRefine((document, context) => {
    const mediaIds = new Set(document.media.map((item) => item.mediaId))
    const footnotes = new Set<string>()
    const refs = new Set<string>()
    const visitInline = (nodes: RichInline[]) => {
      for (const node of nodes) {
        if (node.type === 'footnoteRef') refs.add(node.id)
        if ('children' in node) visitInline(node.children)
      }
    }
    const visit = (blocks: RichBlock[]) => {
      for (const block of blocks) {
        if (block.type === 'image' && !mediaIds.has(block.mediaId)) {
          context.addIssue({
            code: 'custom',
            path: ['blocks'],
            message: `Unknown media ${block.mediaId}`,
          })
        }
        if (block.type === 'footnote') {
          if (footnotes.has(block.id)) {
            context.addIssue({
              code: 'custom',
              path: ['blocks'],
              message: `Duplicate footnote ${block.id}`,
            })
          }
          footnotes.add(block.id)
          visitInline(block.children)
        }
        if (block.type === 'paragraph' || block.type === 'heading') visitInline(block.children)
        if (block.type === 'list') block.items.forEach(visitInline)
        if (block.type === 'taskList') block.items.forEach((item) => visitInline(item.children))
        if (block.type === 'quote') visit(block.blocks)
        if (block.type === 'details') {
          visitInline(block.summary)
          visit(block.blocks)
        }
      }
    }
    visit(document.blocks)
    for (const reference of refs) {
      if (!footnotes.has(reference)) {
        context.addIssue({
          code: 'custom',
          path: ['blocks'],
          message: `Unknown footnote ${reference}`,
        })
      }
    }
  })
export type RichDocument = z.infer<typeof richDocumentSchema>

export const richDocumentCommandSchema = z
  .object({
    schemaVersion: z.literal(2),
    markdown: z.string().trim().min(1).max(32_768),
    document: richDocumentSchema,
  })
  .strict()
export type RichDocumentCommand = z.infer<typeof richDocumentCommandSchema>
