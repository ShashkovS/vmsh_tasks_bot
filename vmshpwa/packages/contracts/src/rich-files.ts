/** Attachment policy, mirrored by models/pwa/rich_files.py; docs/rich-file-attachments.md. */
export const maxRichFileBytes = 50 * 1024 * 1024
export const richFileExtensions = [
  'pdf',
  'doc',
  'docx',
  'xls',
  'xlsx',
  'ppt',
  'pptx',
  'odt',
  'ods',
  'odp',
  'txt',
  'csv',
  'zip',
  '7z',
  'rar',
] as const

export function isRichFileName(filename: string): boolean {
  return (
    filename.length > 0 &&
    filename === filename.trim() &&
    filename === filename.normalize('NFC') &&
    new TextEncoder().encode(filename).length <= 255 &&
    !/[/\\\p{Cc}\p{Cf}]/u.test(filename) &&
    richFileExtensions.some((extension) => filename.toLowerCase().endsWith(`.${extension}`))
  )
}

export function isLocalRichFileUrl(value: string): boolean {
  const match = /^\/pwa-rich-files\/([a-f0-9]{64})\/([^/?#]+)$/u.exec(value)
  if (!match?.[2]) return false
  try {
    const filename = decodeURIComponent(match[2])
    const encoded = encodeURIComponent(filename).replace(
      /[!'()*]/gu,
      (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
    )
    return isRichFileName(filename) && encoded === match[2]
  } catch {
    return false
  }
}
