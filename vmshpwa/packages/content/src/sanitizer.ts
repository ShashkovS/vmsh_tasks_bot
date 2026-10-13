import DOMPurify, { type Config } from 'dompurify'

import { isAllowedWebAssetUrl, isAllowedWebLinkUrl } from '@vmsh/contracts'

const HTML_NAMESPACE = 'http://www.w3.org/1999/xhtml'
const MAXIMUM_HTML_CHARACTERS = 1_000_000

export const semanticHtmlTags = [
  'a',
  'aside',
  'blockquote',
  'br',
  'caption',
  'code',
  'dd',
  'details',
  'div',
  'dl',
  'dt',
  'em',
  'figcaption',
  'figure',
  'h2',
  'h3',
  'h4',
  'hr',
  'img',
  'li',
  'mark',
  'ol',
  'p',
  'pre',
  's',
  'span',
  'strong',
  'sub',
  'summary',
  'sup',
  'table',
  'tbody',
  'td',
  'tfoot',
  'th',
  'thead',
  'time',
  'tr',
  'u',
  'ul',
] as const

const semanticHtmlAttributes = [
  'alt',
  'class',
  'colspan',
  'datetime',
  'decoding',
  'height',
  'href',
  'id',
  'loading',
  'open',
  'reversed',
  'rowspan',
  'scope',
  'src',
  'start',
  'title',
  'type',
  'value',
  'width',
] as const

const attributesByTag: Readonly<Record<string, ReadonlySet<string>>> = {
  a: new Set(['href', 'title']),
  details: new Set(['open']),
  img: new Set(['alt', 'decoding', 'height', 'loading', 'src', 'width']),
  li: new Set(['value']),
  ol: new Set(['reversed', 'start', 'type']),
  td: new Set(['colspan', 'rowspan']),
  th: new Set(['colspan', 'rowspan', 'scope']),
  time: new Set(['datetime']),
}

const globallyAllowedAttributes = new Set(['class', 'id', 'title'])
const allowedSemanticClasses = new Set([
  'vmsh-eq',
  'vmsh-eqno',
  'vmsh-note',
  'vmsh-note-title',
  'vmsh-proof',
  'vmsh-theorem',
])
const canonicalAnchorPattern = /^[a-z][a-z0-9._:-]{0,127}$/u
const semanticHtmlTagSet = new Set<string>(semanticHtmlTags)

function containsUnsupportedRawTag(html: string): boolean {
  if (/<![^>]*>/u.test(html)) return true
  const tagPattern = /<\s*\/?\s*([a-z][a-z0-9:-]*)\b/giu
  for (const match of html.matchAll(tagPattern)) {
    const tag = match[1]?.toLowerCase()
    if (!tag || !semanticHtmlTagSet.has(tag)) return true
  }
  return false
}

const sanitizerConfig = {
  ALLOWED_ATTR: [...semanticHtmlAttributes],
  ALLOWED_NAMESPACES: [HTML_NAMESPACE],
  ALLOWED_TAGS: [...semanticHtmlTags],
  ALLOW_DATA_ATTR: false,
  ALLOW_UNKNOWN_PROTOCOLS: false,
  CUSTOM_ELEMENT_HANDLING: {
    allowCustomizedBuiltInElements: false,
    attributeNameCheck: null,
    tagNameCheck: null,
  },
  FORBID_ATTR: ['style'],
  FORBID_TAGS: ['embed', 'form', 'iframe', 'input', 'math', 'object', 'script', 'style', 'svg'],
  KEEP_CONTENT: true,
  RETURN_DOM_FRAGMENT: true,
  SAFE_FOR_XML: true,
  SANITIZE_DOM: true,
} as const satisfies Config

export type SemanticHtmlSanitizationResult =
  | { ok: true; fragment: DocumentFragment }
  | { ok: false; reason: 'too-large' | 'sanitizer-unavailable' | 'unsupported-markup' }

function isPositiveBoundedInteger(value: string, maximum: number): boolean {
  return /^\d+$/u.test(value) && Number(value) >= 1 && Number(value) <= maximum
}

function hasOnlyAllowedAttributes(element: Element): boolean {
  const tag = element.localName
  const tagAttributes = attributesByTag[tag] ?? new Set<string>()

  for (const attribute of element.attributes) {
    if (!globallyAllowedAttributes.has(attribute.name) && !tagAttributes.has(attribute.name)) {
      return false
    }
    if (attribute.name === 'class') {
      const tokens = attribute.value.split(/\s+/u).filter(Boolean)
      if (tokens.length === 0 || tokens.some((token) => !allowedSemanticClasses.has(token))) {
        return false
      }
    }
    if (attribute.name === 'id' && !canonicalAnchorPattern.test(attribute.value)) return false
    if (attribute.name === 'href' && !isAllowedWebLinkUrl(attribute.value)) return false
    if (attribute.name === 'src' && !isAllowedWebAssetUrl(attribute.value)) return false
    if (attribute.name === 'alt' && attribute.value.trim().length === 0) return false
    if (
      (attribute.name === 'width' || attribute.name === 'height') &&
      !isPositiveBoundedInteger(attribute.value, 20_000)
    ) {
      return false
    }
    if (
      (attribute.name === 'colspan' || attribute.name === 'rowspan') &&
      !isPositiveBoundedInteger(attribute.value, attribute.name === 'colspan' ? 20 : 200)
    ) {
      return false
    }
    if (attribute.name === 'scope' && attribute.value !== 'col' && attribute.value !== 'row') {
      return false
    }
    if (attribute.name === 'loading' && !['eager', 'lazy'].includes(attribute.value)) return false
    if (attribute.name === 'decoding' && !['async', 'auto', 'sync'].includes(attribute.value)) {
      return false
    }
    if (attribute.name === 'type' && !['1', 'A', 'a', 'I', 'i'].includes(attribute.value)) {
      return false
    }
  }

  return tag !== 'img' || (element.hasAttribute('src') && element.hasAttribute('alt'))
}

/**
 * Sanitizes a legacy HTML derivative into a DOM fragment. Returning a fragment
 * avoids a raw string `innerHTML` sink and remains compatible with DOMPurify's
 * Trusted Types policy in browsers that enforce it. Any removed or unsupported
 * node rejects the whole derivative instead of rendering a misleading subset.
 */
export function sanitizeSemanticHtml(html: string): SemanticHtmlSanitizationResult {
  if (html.length > MAXIMUM_HTML_CHARACTERS) return { ok: false, reason: 'too-large' }
  if (!DOMPurify.isSupported) return { ok: false, reason: 'sanitizer-unavailable' }
  // DOMPurify sanitizes a fragment body; browser parsers can move a leading
  // script into an implicit head before DOMPurify sees it. Reject unsupported
  // source tags lexically as well, then let DOMPurify handle malformed markup.
  if (containsUnsupportedRawTag(html)) return { ok: false, reason: 'unsupported-markup' }

  const fragment = DOMPurify.sanitize(html, sanitizerConfig)
  const removedMaterial = DOMPurify.removed.some(
    (removal) => !('element' in removal && (removal.element as Element).localName === 'body'),
  )
  if (removedMaterial) return { ok: false, reason: 'unsupported-markup' }

  for (const element of fragment.querySelectorAll('*')) {
    if (element.namespaceURI !== HTML_NAMESPACE || !hasOnlyAllowedAttributes(element)) {
      return { ok: false, reason: 'unsupported-markup' }
    }
  }

  return { ok: true, fragment }
}
