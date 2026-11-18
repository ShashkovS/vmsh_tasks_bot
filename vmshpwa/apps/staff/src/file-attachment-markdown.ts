import type { StaffRichFile } from '@vmsh/contracts'

/** Preserve filenames as plain labels in the strict parser; rich-file-attachments.md. */
export function fileAttachmentMarkdown(file: StaffRichFile): string {
  const label = file.filename.replace(/([\\`*_[\]<>~|$])/gu, '\\$1')
  return `\n\n[${label}](${file.url})\n`
}
