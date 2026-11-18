import { describe, expect, it } from 'vitest'
import { isLocalRichFileUrl, maxRichFileBytes, richFileExtensions } from './rich-files'
import { richDocumentSchema } from './rich-document'
import { staffRichFileUploadResponseSchema } from './rich-media'

const url = `/pwa-rich-files/${'a'.repeat(64)}/document.pdf`

describe('public Rich Markdown file contract', () => {
  it('validates the shared upload response and exact size boundary', () => {
    const payload = {
      schemaVersion: 1,
      file: {
        url,
        filename: 'document.pdf',
        mimeType: 'application/pdf',
        byteSize: maxRichFileBytes,
      },
      requestId: 'upload',
    }
    expect(staffRichFileUploadResponseSchema.parse(payload)).toEqual(payload)
    expect(
      staffRichFileUploadResponseSchema.safeParse({
        ...payload,
        file: { ...payload.file, byteSize: maxRichFileBytes + 1 },
      }).success,
    ).toBe(false)
    expect(richFileExtensions).toHaveLength(15)
  })

  it('permits canonical local attachments only in links, never images', () => {
    expect(isLocalRichFileUrl(url)).toBe(true)
    expect(
      isLocalRichFileUrl(
        `/pwa-rich-files/${'a'.repeat(64)}/%D0%A4%D0%B0%D0%B9%D0%BB%20%5B1%5D.pdf`,
      ),
    ).toBe(true)
    const document = {
      schemaVersion: 1,
      blocks: [
        {
          type: 'paragraph',
          children: [{ type: 'link', href: url, children: [{ type: 'text', text: 'File' }] }],
        },
      ],
      media: [],
    }
    expect(richDocumentSchema.safeParse(document).success).toBe(true)
    for (const unsafe of [
      url + '?x=1',
      url + '#x',
      '/other/file.pdf',
      '//evil.test/file.pdf',
      `/pwa-rich-files/${'a'.repeat(64)}/%2E%2E%2Ffile.pdf`,
      url.replace('.pdf', '.exe'),
    ]) {
      expect(isLocalRichFileUrl(unsafe)).toBe(false)
    }
    expect(
      richDocumentSchema.safeParse({
        ...document,
        blocks: [{ type: 'image', mediaId: 'file', alt: 'File' }],
        media: [
          {
            mediaId: 'file',
            sourceUrl: url,
            alt: 'File',
            mimeType: 'image/webp',
            width: 1,
            height: 1,
          },
        ],
      }).success,
    ).toBe(false)
  })
})
