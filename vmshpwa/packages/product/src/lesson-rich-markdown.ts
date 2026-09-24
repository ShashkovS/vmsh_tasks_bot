import {
  lessonRichDocumentSchema,
  type LessonRichDocument,
  type LessonVideoBlock,
  type RichBlock,
} from '@vmsh/contracts'

import { RichMarkdownDiagnostic, parseRichMarkdown } from './rich-markdown'
import { normalizeLessonVideoUrl } from './lesson-video'

const directive =
  /(?:^|\n[ \t]*\n)[ \t]*::video\[((?:\\.|[^\]])*)\]\(([^\s)]+)\)[ \t]*(?=\n[ \t]*\n|$)/gu
const iframe = /(?:^|\n[ \t]*\n)[ \t]*(<iframe\b[\s\S]*?<\/iframe>)[ \t]*(?=\n[ \t]*\n|$)/giu

function unescapeTitle(value: string): string {
  return value.replaceAll('\\[', '[').replaceAll('\\]', ']').replaceAll('\\\\', '\\')
}

function protectFencedCode(markdown: string): {
  source: string
  restore: (value: string) => string
} {
  const fences: string[] = []
  const lines = markdown.match(/.*(?:\n|$)/gu) ?? []
  let active: { marker: '`' | '~'; width: number; value: string } | null = null
  let source = ''
  for (const line of lines) {
    const opening = /^\s{0,3}(`{3,}|~{3,})/u.exec(line)
    if (active === null && opening) {
      active = { marker: opening[1]?.[0] as '`' | '~', width: opening[1]?.length ?? 3, value: line }
      continue
    }
    if (active !== null) {
      active.value += line
      const closing = new RegExp(`^\\s{0,3}${active.marker}{${active.width},}\\s*$`, 'u')
      if (closing.test(line.trimEnd())) {
        const index = fences.push(active.value) - 1
        source += `\n\nvmshfencedcodetoken${index}\n\n`
        active = null
      }
      continue
    }
    source += line
  }
  if (active !== null) source += active.value
  return {
    source,
    restore: (value) =>
      value.replace(
        /vmshfencedcodetoken(\d+)/gu,
        (_whole, index: string) => fences[Number(index)] ?? '',
      ),
  }
}

function rejectNestedVideos(markdown: string): void {
  if (/^\s{0,3}(?:>\s*|[-*+]\s+|\d+[.)]\s+)(?:::video\[|<iframe\b)/mu.test(markdown)) {
    throw new RichMarkdownDiagnostic('Видео разрешено только отдельным корневым блоком')
  }
}

function extractVideos(markdown: string): { source: string; videos: LessonVideoBlock[] } {
  const protectedCode = protectFencedCode(markdown)
  rejectNestedVideos(protectedCode.source)
  const videos: LessonVideoBlock[] = []
  const replace = (_whole: string, title: string, source: string) => {
    const index = videos.length
    videos.push(normalizeLessonVideoUrl(source, unescapeTitle(title)))
    return `\n\nvmshlessonvideotoken${index}\n\n`
  }
  let source = protectedCode.source.replace(directive, replace)
  source = source.replace(iframe, (_whole, frame: string) => {
    const index = videos.length
    videos.push(normalizeLessonVideoUrl(frame))
    return `\n\nvmshlessonvideotoken${index}\n\n`
  })
  return { source: protectedCode.restore(source), videos }
}

/** Lesson-only Markdown parser; ordinary Rich Markdown remains unchanged. */
export function parseLessonRichMarkdown(markdown: string): LessonRichDocument {
  const extracted = extractVideos(markdown.trimEnd())
  const ordinary = parseRichMarkdown(extracted.source)
  const blocks = ordinary.blocks.map((block): RichBlock | LessonVideoBlock => {
    if (
      block.type === 'paragraph' &&
      block.children.length === 1 &&
      block.children[0]?.type === 'text'
    ) {
      const match = /^vmshlessonvideotoken(\d+)$/u.exec(block.children[0].text)
      if (match) {
        const video = extracted.videos[Number(match[1])]
        if (!video) throw new RichMarkdownDiagnostic('Видео не найдено')
        return video
      }
    }
    return block
  })
  return lessonRichDocumentSchema.parse({ ...ordinary, blocks })
}
