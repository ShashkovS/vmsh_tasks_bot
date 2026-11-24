import { z } from 'zod'
import { lessonRichDocumentSchema } from '../packages/contracts/src/lesson-rich-document'
import { i18n } from '@lingui/core'
import { I18nProvider } from '@lingui/react'
import { renderToStaticMarkup } from 'react-dom/server'
import exportCss from './worksheet.css?raw'
import contentCss from '../packages/content/src/content.css?raw'
import { webContentDocumentSchema } from '../packages/contracts/src/content'
import { readFileSync } from 'node:fs'
import { SemanticMathDocument } from '../packages/content/src/math-document'
import { LessonRichDocumentView } from '../packages/product/src/lesson-blocks'
import { parseLessonRichMarkdown } from '../packages/product/src/lesson-rich-markdown'
import { messages as ru } from '../apps/staff/src/i18n/catalog-ru'
import { messages as en } from '../apps/staff/src/i18n/catalog-en'

// The CLI receives lesson projections from admin_mcp/render.py. Validate with the PWA contracts before JSX.
const envelope = z.object({ locale: z.enum(['ru', 'en']).optional() })
const input = z
  .discriminatedUnion('action', [
    envelope.extend({ action: z.literal('markdown'), markdown: z.string().max(32768) }),
    envelope.extend({ action: z.literal('block'), document: lessonRichDocumentSchema }),
    envelope.extend({ action: z.literal('render'), documents: z.array(webContentDocumentSchema) }),
  ])
  .parse(JSON.parse(readFileSync(0, 'utf8')))
const locale = input.locale === 'en' ? 'en' : 'ru'
i18n.loadAndActivate({ locale, messages: locale === 'en' ? en : ru })
if (input.action === 'markdown') {
  process.stdout.write(JSON.stringify(parseLessonRichMarkdown(input.markdown)))
} else if (input.action === 'block') {
  process.stdout.write(
    renderToStaticMarkup(
      <I18nProvider i18n={i18n}>
        <LessonRichDocumentView document={input.document} idPrefix="lesson" />
      </I18nProvider>,
    ),
  )
} else {
  process.stdout.write(
    renderToStaticMarkup(
      <I18nProvider i18n={i18n}>
        <style>{contentCss.replace(/@import[^;]+;|@font-face\s*\{[^}]*\}/g, '')}</style>
        <style>{exportCss}</style>
        {input.documents.map((document, index) => (
          <SemanticMathDocument key={index} document={document} />
        ))}
      </I18nProvider>,
    ),
  )
}
