import { describe, expect, it } from 'vitest'

import webDocumentFixture from '../fixtures/content/web-document.v1.json'
import goldenLesson39 from '../fixtures/content/golden/lesson-39-n.v1.json'
import goldenLesson40 from '../fixtures/content/golden/lesson-40-n.v1.json'
import goldenLesson41 from '../fixtures/content/golden/lesson-41-n.v1.json'
import pythonCompilerPreviewFixture from '../fixtures/content/python-compiler-preview.v1.json'

import {
  goldenContentComparisonFixtureSchema,
  isAllowedWebAssetUrl,
  isAllowedWebLinkUrl,
  webContentContractFixtureSchema,
  webContentDocumentSchema,
  webContentPreviewContractFixtureSchema,
  webContentStructuralLimits,
} from './content'

describe('web content derivative contract', () => {
  it.each([goldenLesson39, goldenLesson40, goldenLesson41])(
    'keeps the real lesson $lessonNumber condition bound to source and PDF hashes',
    (fixture) => {
      const parsed = goldenContentComparisonFixtureSchema.parse(fixture)
      expect(parsed.webDocument.problems).toHaveLength(11)
      expect(parsed.telegram.html).toContain('<tg-math>')
      expect(parsed.webDocument.sourceSha256).toBe(parsed.source.sha256)
    },
  )

  it('keeps the versioned representative fixture in parity', () => {
    expect(webContentContractFixtureSchema.parse(webDocumentFixture)).toEqual(webDocumentFixture)
  })

  it('accepts the deterministic Python compiler preview without secret sibling branches', () => {
    const parsed = webContentPreviewContractFixtureSchema.parse(pythonCompilerPreviewFixture)
    expect(parsed).toEqual(pythonCompilerPreviewFixture)
    expect(parsed.document.revisionId).toBeNull()

    const forbiddenKeys = new Set(['answer', 'hint', 'solution'])
    const stack: unknown[] = [parsed.document]
    while (stack.length > 0) {
      const value = stack.pop()
      if (typeof value !== 'object' || value === null) continue
      if (Array.isArray(value)) {
        for (const child of value as unknown[]) stack.push(child)
        continue
      }
      for (const [key, child] of Object.entries(value)) {
        expect(forbiddenKeys.has(key)).toBe(false)
        stack.push(child)
      }
    }
  })

  it('fails closed for duplicate problem ordinals and unknown blocks', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    expect(() =>
      webContentDocumentSchema.parse({
        ...document,
        problems: [document.problems[0], structuredClone(document.problems[0])],
      }),
    ).toThrow(/unique/u)
    expect(() =>
      webContentDocumentSchema.parse({
        ...document,
        introduction: [{ type: 'raw_html', html: '<b>unsafe boundary</b>' }],
      }),
    ).toThrow()
  })

  it('rejects pathological depth before recursive block parsing', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    let nested: unknown = { type: 'paragraph', children: [] }
    for (let index = 0; index <= webContentStructuralLimits.maximumJsonDepth; index += 1) {
      nested = { type: 'subpart', label: 'а', blocks: [nested] }
    }

    expect(() =>
      webContentDocumentSchema.parse({ ...document, introduction: [nested], problems: [] }),
    ).toThrow(/nesting/u)
  })

  it('rejects a payload whose aggregate text exceeds the document budget', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    expect(() =>
      webContentDocumentSchema.parse({
        ...document,
        introduction: [
          {
            type: 'paragraph',
            children: [
              { type: 'text', value: 'x'.repeat(webContentStructuralLimits.maximumTextCharacters) },
            ],
          },
        ],
        problems: [],
      }),
    ).toThrow(/text/u)
  })

  it.each([
    ['/content/figure.svg', true],
    ['https://media.example.test/a.webp?version=1', true],
    ['http://media.example.test/a.webp', false],
    ['//media.example.test/a.webp', false],
    ['https://user:secret@media.example.test/a.webp', false],
    ['javascript:alert(1)', false],
    [' data:image/svg+xml,<svg/>', false],
  ])('applies the explicit external-asset URL policy to %s', (url, allowed) => {
    expect(isAllowedWebAssetUrl(url)).toBe(allowed)
  })

  it.each([
    ['#problem-1', true],
    ['/student/tasks/41', true],
    ['https://example.test/article', true],
    ['mailto:vmsh@179.ru', true],
    ['tel:+123', false],
    ['data:text/html,unsafe', false],
  ])('applies the explicit content-link URL policy to %s', (url, allowed) => {
    expect(isAllowedWebLinkUrl(url)).toBe(allowed)
  })
})
