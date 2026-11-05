import type { TelegramEntity, TelegramTextBlock } from './telegram-post'

const markers = [
  ['**', 'bold'],
  ['__', 'underline'],
  ['~~', 'strike'],
  ['||', 'spoiler'],
  ['`', 'code'],
  ['_', 'italic'],
] as const

/** Inline subset shared by the Staff editor and the server-side Telegram projection. */
export function parseTelegramMarkdown(markdown: string): TelegramTextBlock {
  let text = ''
  const entities: TelegramEntity[] = []
  let index = 0
  let literalStart = 0

  const append = (value: string, entity?: Omit<TelegramEntity, 'offset' | 'length'>) => {
    if (value === '') return
    const offset = text.length
    text += value
    if (entity) entities.push({ ...entity, offset, length: value.length })
  }

  while (index < markdown.length) {
    if (markdown[index] === '\\' && index + 1 < markdown.length) {
      append(markdown.slice(literalStart, index))
      append(markdown[index + 1] ?? '')
      index += 2
      literalStart = index
      continue
    }
    if (markdown[index] === '[') {
      const labelEnd = markdown.indexOf('](', index + 1)
      const hrefEnd = labelEnd >= 0 ? markdown.indexOf(')', labelEnd + 2) : -1
      const href = labelEnd >= 0 && hrefEnd >= 0 ? markdown.slice(labelEnd + 2, hrefEnd) : ''
      if (labelEnd > index + 1 && hrefEnd > labelEnd + 2 && /^https?:\/\//u.test(href)) {
        append(markdown.slice(literalStart, index))
        append(markdown.slice(index + 1, labelEnd), { type: 'link', href })
        index = hrefEnd + 1
        literalStart = index
        continue
      }
    }
    let matched = false
    for (const [marker, type] of markers) {
      if (!markdown.startsWith(marker, index)) continue
      const end = markdown.indexOf(marker, index + marker.length)
      if (end <= index + marker.length) continue
      append(markdown.slice(literalStart, index))
      append(markdown.slice(index + marker.length, end), { type })
      index = end + marker.length
      literalStart = index
      matched = true
      break
    }
    if (!matched) index += 1
  }
  append(markdown.slice(literalStart))
  return { kind: 'text', text, ...(entities.length === 0 ? {} : { entities }) }
}
