/*
 * View-model for a Telegram-sourced news post rendered in the PWA. Text carries
 * Telegram entities (offset/length based); blocks add quotes and a math
 * extension. Editorial state distinguishes a source revision, a local editorial
 * override, hidden/source-deleted and a delivery error.
 */
export type TelegramEntityType =
  'bold' | 'italic' | 'underline' | 'strike' | 'code' | 'link' | 'spoiler' | 'mark' | 'sub' | 'sup'

export interface TelegramEntity {
  type: TelegramEntityType
  offset: number
  length: number
  href?: string
}

export interface TelegramTextBlock {
  kind: 'text'
  text: string
  entities?: TelegramEntity[]
}

export interface TelegramQuoteBlock {
  kind: 'quote'
  text: string
  entities?: TelegramEntity[]
}

export interface TelegramMathBlock {
  kind: 'math'
  /** Sanitized HTML with math delimiters, rendered via a `renderMath` hook. */
  html: string
}

export interface TelegramHeadingBlock {
  kind: 'heading'
  level: 1 | 2 | 3 | 4 | 5 | 6
  text: string
  entities?: TelegramEntity[]
}

export interface TelegramListBlock {
  kind: 'list'
  ordered?: boolean
  start?: number
  items: { text: string; entities?: TelegramEntity[] }[]
}

export interface TelegramCodeBlock {
  kind: 'code'
  code: string
  language?: string
}

export interface TelegramTableBlock {
  kind: 'table'
  caption?: string
  headers?: string[]
  rows: string[][]
}

export interface TelegramDetailsBlock {
  kind: 'details'
  summary: string
  open?: boolean
  blocks: TelegramBlock[]
}

export interface TelegramDividerBlock {
  kind: 'divider'
}

export type TelegramBlock =
  | TelegramTextBlock
  | TelegramQuoteBlock
  | TelegramMathBlock
  | TelegramHeadingBlock
  | TelegramListBlock
  | TelegramCodeBlock
  | TelegramTableBlock
  | TelegramDetailsBlock
  | TelegramDividerBlock

export interface TelegramPhoto {
  kind: 'photo'
  previewUrl?: string
  alt?: string
}

export interface TelegramVideo {
  kind: 'video'
  previewUrl?: string
  durationLabel?: string
  alt?: string
}

export interface TelegramDocument {
  kind: 'document'
  name: string
  sizeLabel?: string
  url?: string
}

export type TelegramMedia = TelegramPhoto | TelegramVideo | TelegramDocument

export interface TelegramAttribution {
  author?: string
  channel?: string
  forwardedFrom?: string
}

export type TelegramPostState =
  'published' | 'source-revised' | 'local-override' | 'hidden' | 'source-deleted' | 'delivery-error'

export interface TelegramPostView {
  id: string
  attribution?: TelegramAttribution | undefined
  blocks: TelegramBlock[]
  media?: TelegramMedia[] | undefined
  at?: string | undefined
  editedAt?: string | undefined
  state?: TelegramPostState | undefined
}

export interface RichTextSegment {
  text: string
  entity?: TelegramEntity
}

/** Split text into plain and entity-wrapped segments (non-overlapping). */
export function toRichTextSegments(text: string, entities: TelegramEntity[]): RichTextSegment[] {
  const sorted = [...entities].sort((a, b) => a.offset - b.offset)
  const segments: RichTextSegment[] = []
  let cursor = 0
  for (const entity of sorted) {
    if (entity.offset < cursor) continue
    if (entity.offset > cursor) segments.push({ text: text.slice(cursor, entity.offset) })
    segments.push({ text: text.slice(entity.offset, entity.offset + entity.length), entity })
    cursor = entity.offset + entity.length
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) })
  return segments
}
