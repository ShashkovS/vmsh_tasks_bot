import { z } from 'zod'

import { publicIdSchema } from './auth'

/**
 * Phase-2 browser derivative contract. It deliberately contains only the
 * selected material kind, so a condition payload cannot accidentally expose
 * hint/solution branches from the compiler AST. See
 * `docs/latex-content-pipeline.md` and `packages/content/src/math-document.tsx`.
 */

export const WEB_CONTENT_CONTRACT_VERSION = 1 as const
const webContentContractVersionSchema = z.literal(WEB_CONTENT_CONTRACT_VERSION)

export const webContentStructuralLimits = {
  maximumJsonDepth: 32,
  maximumBlockDepth: 16,
  maximumNodes: 20_000,
  maximumTextCharacters: 1_000_000,
} as const

const boundedTextSchema = z.string().max(32_768)
const nonEmptyTextSchema = z.string().trim().min(1).max(2_000)
const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/, 'Expected a lowercase SHA-256 digest')
const anchorSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[a-z][a-z0-9._:-]*$/, 'Anchor must be a canonical lowercase token')

function hasUnsafeUrlCharacters(value: string): boolean {
  return (
    value !== value.trim() ||
    value.includes('\\') ||
    [...value].some((character) => {
      const codePoint = character.codePointAt(0)
      return codePoint !== undefined && (codePoint <= 31 || codePoint === 127)
    })
  )
}

export function isAllowedWebAssetUrl(value: string): boolean {
  if (hasUnsafeUrlCharacters(value)) return false
  if (/^\/(?!\/)/u.test(value)) return true

  try {
    const url = new URL(value)
    return (
      url.protocol === 'https:' &&
      url.hostname.length > 0 &&
      url.username.length === 0 &&
      url.password.length === 0
    )
  } catch {
    return false
  }
}

export function isAllowedWebLinkUrl(value: string): boolean {
  if (hasUnsafeUrlCharacters(value)) return false
  if (/^#[a-z][a-z0-9._:-]*$/u.test(value)) return true
  if (isAllowedWebAssetUrl(value)) return true

  try {
    const url = new URL(value)
    return url.protocol === 'mailto:' && url.pathname.length > 0
  } catch {
    return false
  }
}

export const webAssetUrlSchema = z.string().max(4_096).refine(isAllowedWebAssetUrl, {
  message: 'Asset URL must be root-relative or credential-free HTTPS',
})
export const webLinkUrlSchema = z.string().max(4_096).refine(isAllowedWebLinkUrl, {
  message: 'Link URL must be an anchor, root-relative, HTTPS or mailto URL',
})

export type WebInlineNode =
  | { type: 'text'; value: string }
  | { type: 'math'; latex: string }
  | { type: 'code'; value: string }
  | { type: 'strong'; children: WebInlineNode[] }
  | { type: 'emphasis'; children: WebInlineNode[] }
  | { type: 'link'; href: string; children: WebInlineNode[] }

export const webInlineNodeSchema: z.ZodType<WebInlineNode> = z.lazy(() =>
  z.discriminatedUnion('type', [
    z.object({ type: z.literal('text'), value: boundedTextSchema }).strict(),
    z.object({ type: z.literal('math'), latex: z.string().min(1).max(8_192) }).strict(),
    z.object({ type: z.literal('code'), value: z.string().max(8_192) }).strict(),
    z
      .object({
        type: z.literal('strong'),
        children: z.array(webInlineNodeSchema).max(1_000),
      })
      .strict(),
    z
      .object({
        type: z.literal('emphasis'),
        children: z.array(webInlineNodeSchema).max(1_000),
      })
      .strict(),
    z
      .object({
        type: z.literal('link'),
        href: webLinkUrlSchema,
        children: z.array(webInlineNodeSchema).min(1).max(1_000),
      })
      .strict(),
  ]),
)

export interface WebContentTableCell {
  type: 'header' | 'data'
  children: WebInlineNode[]
  columnSpan?: number | undefined
  rowSpan?: number | undefined
  scope?: 'col' | 'row' | undefined
}

export interface WebFigureAvailableAsset {
  status: 'available'
  assetId: string
  contentSha256: string
  src: string
  mediaType: 'image/svg+xml' | 'image/webp' | 'image/png' | 'image/jpeg'
  width: number
  height: number
}

export interface WebFigureMissingAsset {
  status: 'missing'
  logicalName: string
}

export type WebContentBlock =
  | { type: 'paragraph'; children: WebInlineNode[] }
  | { type: 'heading'; level: 2 | 3 | 4; anchor?: string | undefined; children: WebInlineNode[] }
  | { type: 'formula'; latex: string; anchor?: string | undefined; label?: string | undefined }
  | {
      type: 'list'
      ordered: boolean
      start?: number | undefined
      items: WebContentBlock[][]
    }
  | {
      type: 'table'
      caption?: WebInlineNode[] | undefined
      rows: WebContentTableCell[][]
    }
  | {
      type: 'figure'
      alt: string
      caption?: WebInlineNode[] | undefined
      asset: WebFigureAvailableAsset | WebFigureMissingAsset
    }
  | { type: 'subpart'; label: string; blocks: WebContentBlock[] }
  | {
      type: 'callout'
      kind: 'note' | 'theorem' | 'proof'
      title?: string | undefined
      blocks: WebContentBlock[]
    }
  | { type: 'divider' }

const webContentTableCellSchema: z.ZodType<WebContentTableCell> = z
  .object({
    type: z.enum(['header', 'data']),
    children: z.array(webInlineNodeSchema).max(1_000),
    columnSpan: z.number().int().min(1).max(20).optional(),
    rowSpan: z.number().int().min(1).max(200).optional(),
    scope: z.enum(['col', 'row']).optional(),
  })
  .strict()

const webFigureAvailableAssetSchema = z
  .object({
    status: z.literal('available'),
    assetId: publicIdSchema,
    contentSha256: sha256Schema,
    src: webAssetUrlSchema,
    mediaType: z.enum(['image/svg+xml', 'image/webp', 'image/png', 'image/jpeg']),
    width: z.number().int().positive().max(20_000),
    height: z.number().int().positive().max(20_000),
  })
  .strict()

const webFigureMissingAssetSchema = z
  .object({
    status: z.literal('missing'),
    logicalName: nonEmptyTextSchema,
  })
  .strict()

export const webContentBlockSchema: z.ZodType<WebContentBlock> = z.lazy(() =>
  z.discriminatedUnion('type', [
    z
      .object({
        type: z.literal('paragraph'),
        children: z.array(webInlineNodeSchema).max(1_000),
      })
      .strict(),
    z
      .object({
        type: z.literal('heading'),
        level: z.union([z.literal(2), z.literal(3), z.literal(4)]),
        anchor: anchorSchema.optional(),
        children: z.array(webInlineNodeSchema).min(1).max(1_000),
      })
      .strict(),
    z
      .object({
        type: z.literal('formula'),
        latex: z.string().min(1).max(16_384),
        anchor: anchorSchema.optional(),
        label: z.string().trim().min(1).max(80).optional(),
      })
      .strict(),
    z
      .object({
        type: z.literal('list'),
        ordered: z.boolean(),
        start: z.number().int().min(1).max(10_000).optional(),
        items: z.array(z.array(webContentBlockSchema).min(1).max(100)).min(1).max(1_000),
      })
      .strict(),
    z
      .object({
        type: z.literal('table'),
        caption: z.array(webInlineNodeSchema).max(1_000).optional(),
        rows: z.array(z.array(webContentTableCellSchema).min(1).max(20)).min(1).max(200),
      })
      .strict(),
    z
      .object({
        type: z.literal('figure'),
        alt: nonEmptyTextSchema,
        caption: z.array(webInlineNodeSchema).max(1_000).optional(),
        asset: z.discriminatedUnion('status', [
          webFigureAvailableAssetSchema,
          webFigureMissingAssetSchema,
        ]),
      })
      .strict(),
    z
      .object({
        type: z.literal('subpart'),
        label: nonEmptyTextSchema,
        blocks: z.array(webContentBlockSchema).min(1).max(1_000),
      })
      .strict(),
    z
      .object({
        type: z.literal('callout'),
        kind: z.enum(['note', 'theorem', 'proof']),
        title: nonEmptyTextSchema.optional(),
        blocks: z.array(webContentBlockSchema).min(1).max(1_000),
      })
      .strict(),
    z.object({ type: z.literal('divider') }).strict(),
  ]),
)

export const webContentProblemSchema = z
  .object({
    ordinal: z.number().int().positive(),
    sourceItem: z.string().trim().min(1).max(80).nullable(),
    title: z.string().trim().min(1).max(500).nullable(),
    blocks: z.array(webContentBlockSchema).min(1).max(2_000),
    // Content between this problem and the next one belongs to the document,
    // not to the problem's submission/review controls.
    trailingBlocks: z.array(webContentBlockSchema).max(2_000).optional(),
  })
  .strict()
export type WebContentProblem = z.infer<typeof webContentProblemSchema>

const webContentDocumentBaseSchema = z
  .object({
    contractVersion: webContentContractVersionSchema,
    sourceSha256: sha256Schema,
    materialKind: z.enum(['condition', 'hint', 'solution']),
    title: z.string().trim().min(1).max(500).nullable(),
    introduction: z.array(webContentBlockSchema).max(2_000),
    problems: z.array(webContentProblemSchema).max(2_000),
  })
  .strict()

function refineWebContentDocument(
  document: z.infer<typeof webContentDocumentBaseSchema>,
  context: z.RefinementCtx,
): void {
  const ordinals = new Set<number>()
  document.problems.forEach((problem, index) => {
    if (ordinals.has(problem.ordinal)) {
      context.addIssue({
        code: 'custom',
        message: 'Problem ordinals must be unique within one derivative',
        path: ['problems', index, 'ordinal'],
      })
    }
    ordinals.add(problem.ordinal)
  })

  const stack = [
    ...document.introduction.map((block) => ({ block, depth: 1 })),
    ...document.problems.flatMap((problem) =>
      [...problem.blocks, ...(problem.trailingBlocks ?? [])].map((block) => ({
        block,
        depth: 1,
      })),
    ),
  ]
  while (stack.length > 0) {
    const current = stack.pop()
    if (!current) break
    if (current.depth > webContentStructuralLimits.maximumBlockDepth) {
      context.addIssue({
        code: 'custom',
        message: `Content block nesting must not exceed ${webContentStructuralLimits.maximumBlockDepth}`,
        path: ['problems'],
      })
      break
    }
    if (current.block.type === 'list') {
      for (const item of current.block.items) {
        for (const block of item) stack.push({ block, depth: current.depth + 1 })
      }
    } else if (current.block.type === 'subpart' || current.block.type === 'callout') {
      for (const block of current.block.blocks) {
        stack.push({ block, depth: current.depth + 1 })
      }
    }
  }
}

const webContentDocumentShapeSchema = webContentDocumentBaseSchema
  .extend({ revisionId: publicIdSchema })
  .strict()
  .superRefine(refineWebContentDocument)

const webContentPreviewDocumentShapeSchema = webContentDocumentBaseSchema
  .extend({ revisionId: z.null() })
  .strict()
  .superRefine(refineWebContentDocument)

function checkBoundedUnknownStructure(value: unknown, context: z.RefinementCtx): void {
  const stack: Array<{ value: unknown; depth: number }> = [{ value, depth: 0 }]
  const visited = new Set<object>()
  let nodes = 0
  let textCharacters = 0

  while (stack.length > 0) {
    const current = stack.pop()
    if (!current) break
    nodes += 1
    if (nodes > webContentStructuralLimits.maximumNodes) {
      context.addIssue({
        code: 'custom',
        message: `Content payload must not exceed ${webContentStructuralLimits.maximumNodes} JSON nodes`,
      })
      return
    }
    if (current.depth > webContentStructuralLimits.maximumJsonDepth) {
      context.addIssue({
        code: 'custom',
        message: `Content payload nesting must not exceed ${webContentStructuralLimits.maximumJsonDepth}`,
      })
      return
    }
    if (typeof current.value === 'string') {
      textCharacters += current.value.length
      if (textCharacters > webContentStructuralLimits.maximumTextCharacters) {
        context.addIssue({
          code: 'custom',
          message: `Content payload text must not exceed ${webContentStructuralLimits.maximumTextCharacters} characters`,
        })
        return
      }
      continue
    }
    if (typeof current.value !== 'object' || current.value === null) continue
    if (visited.has(current.value)) {
      context.addIssue({ code: 'custom', message: 'Content payload must be an acyclic JSON value' })
      return
    }
    visited.add(current.value)
    const children = Array.isArray(current.value)
      ? current.value
      : Object.values(current.value as Record<string, unknown>)
    for (const child of children) stack.push({ value: child, depth: current.depth + 1 })
  }
}

// The shallow unknown preflight runs before recursive Zod parsing. This keeps a
// hostile deeply nested payload from reaching the recursive block schema.
export const webContentDocumentSchema = z
  .unknown()
  .superRefine(checkBoundedUnknownStructure)
  .pipe(webContentDocumentShapeSchema)
export type WebContentDocument = z.infer<typeof webContentDocumentSchema>

/** Pre-persistence compiler preview; never use this schema for a public read API. */
export const webContentPreviewDocumentSchema = z
  .unknown()
  .superRefine(checkBoundedUnknownStructure)
  .pipe(webContentPreviewDocumentShapeSchema)
export type WebContentPreviewDocument = z.infer<typeof webContentPreviewDocumentSchema>

export const webContentPreviewContractFixtureSchema = z
  .object({
    fixtureVersion: webContentContractVersionSchema,
    document: webContentPreviewDocumentSchema,
  })
  .strict()
export type WebContentPreviewContractFixture = z.infer<
  typeof webContentPreviewContractFixtureSchema
>

export const webContentContractFixtureSchema = z
  .object({
    fixtureVersion: webContentContractVersionSchema,
    document: webContentDocumentSchema,
  })
  .strict()
export type WebContentContractFixture = z.infer<typeof webContentContractFixtureSchema>

/**
 * Real-source visual-acceptance fixture shared by Storybook and corpus checks.
 * This is not an API payload: source/PDF paths exist only to bind the rendered
 * comparison to `_vmsh_examples`. See `docs/testing-strategy.md`.
 */
export const goldenContentComparisonFixtureSchema = z
  .object({
    fixtureVersion: webContentContractVersionSchema,
    corpusId: z
      .string()
      .min(1)
      .max(128)
      .regex(/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/),
    lessonNumber: z.number().int().nonnegative().max(10_000),
    groupCode: z.string().min(1).max(16),
    source: z
      .object({
        path: z.string().startsWith('_vmsh_examples/').max(512),
        sha256: sha256Schema,
      })
      .strict(),
    referencePdf: z
      .object({
        path: z.string().startsWith('_vmsh_examples/').endsWith('.pdf').max(512),
        sha256: sha256Schema,
      })
      .strict(),
    webDocument: webContentDocumentSchema,
    telegram: z
      .object({
        rendererVersion: z.string().trim().min(1).max(128),
        sha256: sha256Schema,
        html: z.string().min(1).max(32_768),
      })
      .strict(),
  })
  .strict()
  .superRefine((fixture, context) => {
    if (fixture.webDocument.materialKind !== 'condition') {
      context.addIssue({
        code: 'custom',
        message: 'Golden condition corpus must contain a condition document',
        path: ['webDocument', 'materialKind'],
      })
    }
    if (fixture.webDocument.sourceSha256 !== fixture.source.sha256) {
      context.addIssue({
        code: 'custom',
        message: 'Golden document must be bound to the exact source hash',
        path: ['webDocument', 'sourceSha256'],
      })
    }
  })
export type GoldenContentComparisonFixture = z.infer<typeof goldenContentComparisonFixtureSchema>
