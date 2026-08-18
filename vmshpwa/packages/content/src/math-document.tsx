import { Fragment, type CSSProperties, type ReactNode } from 'react'

import type {
  WebContentBlock,
  WebContentDocument,
  WebContentProblem,
  WebContentTableCell,
  WebInlineNode,
} from '@vmsh/contracts'
import { cn } from '@vmsh/ui'

import { MathExpression } from './katex-rendering'
import { ZoomableAssetFigure } from './zoomable-asset-figure'

export interface MathDocumentProps {
  title?: string
  children: ReactNode
  className?: string
}

export function MathDocument({ title, children, className }: MathDocumentProps) {
  return (
    <article className={cn('vmsh-math-content', className)} data-slot="math-document">
      {title ? <h1 className="vmsh-document-title">{title}</h1> : null}
      <div className="vmsh-math-body">{children}</div>
    </article>
  )
}

function InlineNodes({ nodes, path }: { nodes: WebInlineNode[]; path: string }) {
  return nodes.map((node, index) => {
    const key = `${path}-${index}`
    switch (node.type) {
      case 'text':
        return <Fragment key={key}>{node.value}</Fragment>
      case 'math':
        return <MathExpression key={key} latex={node.latex} />
      case 'code':
        return <code key={key}>{node.value}</code>
      case 'strong':
        return (
          <strong key={key}>
            <InlineNodes nodes={node.children} path={key} />
          </strong>
        )
      case 'emphasis':
        return (
          <em key={key}>
            <InlineNodes nodes={node.children} path={key} />
          </em>
        )
      case 'link':
        return (
          <a href={node.href} key={key}>
            <InlineNodes nodes={node.children} path={key} />
          </a>
        )
    }
  })
}

function HeadingBlock({
  block,
  path,
}: {
  block: Extract<WebContentBlock, { type: 'heading' }>
  path: string
}) {
  const content = <InlineNodes nodes={block.children} path={`${path}-inline`} />
  if (block.level === 2)
    return (
      <h2 className="vmsh-content-heading" id={block.anchor}>
        {content}
      </h2>
    )
  if (block.level === 3)
    return (
      <h3 className="vmsh-content-heading" id={block.anchor}>
        {content}
      </h3>
    )
  return (
    <h4 className="vmsh-content-heading" id={block.anchor}>
      {content}
    </h4>
  )
}

function TableCell({ cell, path }: { cell: WebContentTableCell; path: string }) {
  const props = {
    colSpan: cell.columnSpan,
    rowSpan: cell.rowSpan,
  }
  if (cell.type === 'header') {
    return (
      <th {...props} scope={cell.scope}>
        <InlineNodes nodes={cell.children} path={path} />
      </th>
    )
  }
  return (
    <td {...props}>
      <InlineNodes nodes={cell.children} path={path} />
    </td>
  )
}

/* eslint-disable jsx-a11y/no-noninteractive-tabindex -- Axe requires each overflow table region to be keyboard-focusable. */
interface ContentBlocksProps {
  blocks: WebContentBlock[]
  path: string
  problem?: WebContentProblem
  renderAfterSubpart?: (problem: WebContentProblem, label: string) => ReactNode
  renderSubpartActions?: (problem: WebContentProblem, label: string) => ReactNode
}

function ContentBlocks({
  blocks,
  path,
  problem,
  renderAfterSubpart,
  renderSubpartActions,
}: ContentBlocksProps) {
  return blocks.map((block, index) => {
    const key = `${path}-${index}`
    switch (block.type) {
      case 'paragraph':
        return (
          <p key={key}>
            <InlineNodes nodes={block.children} path={`${key}-inline`} />
          </p>
        )
      case 'heading':
        return <HeadingBlock block={block} key={key} path={key} />
      case 'formula':
        return (
          <div className="vmsh-eq" id={block.anchor} key={key}>
            <MathExpression display latex={block.latex} />
            {block.label ? <span className="vmsh-eqno">{block.label}</span> : null}
          </div>
        )
      case 'list': {
        const ListTag = block.ordered ? 'ol' : 'ul'
        return (
          <ListTag key={key} start={block.ordered ? block.start : undefined}>
            {block.items.map((item, itemIndex) => (
              <li key={`${key}-item-${itemIndex}`}>
                <ContentBlocks
                  blocks={item}
                  path={`${key}-item-${itemIndex}`}
                  {...(problem === undefined ? {} : { problem })}
                  {...(renderAfterSubpart === undefined ? {} : { renderAfterSubpart })}
                  {...(renderSubpartActions === undefined ? {} : { renderSubpartActions })}
                />
              </li>
            ))}
          </ListTag>
        )
      }
      case 'table':
        return (
          <div
            aria-label="Таблица с горизонтальной прокруткой"
            className="vmsh-scroll-x"
            key={key}
            role="region"
            tabIndex={0}
          >
            <table>
              {block.caption ? (
                <caption>
                  <InlineNodes nodes={block.caption} path={`${key}-caption`} />
                </caption>
              ) : null}
              <tbody>
                {block.rows.map((row, rowIndex) => (
                  <tr key={`${key}-row-${rowIndex}`}>
                    {row.map((cell, cellIndex) => (
                      <TableCell
                        cell={cell}
                        key={`${key}-cell-${rowIndex}-${cellIndex}`}
                        path={`${key}-cell-${rowIndex}-${cellIndex}`}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      case 'figure':
        if (block.asset.status === 'missing') {
          return (
            <figure
              className="vmsh-asset-figure"
              data-float-hint={block.floatHint}
              key={key}
              style={
                block.widthHint
                  ? ({ '--vmsh-source-width': block.widthHint } as CSSProperties)
                  : undefined
              }
            >
              <div className="vmsh-figure-missing" role="status">
                <strong>Рисунок пока недоступен.</strong>
                <span>{block.alt}</span>
              </div>
              {block.caption ? (
                <figcaption>
                  <InlineNodes nodes={block.caption} path={`${key}-caption`} />
                </figcaption>
              ) : null}
            </figure>
          )
        }
        return (
          <ZoomableAssetFigure
            alt={block.alt}
            asset={block.asset}
            caption={
              block.caption ? (
                <InlineNodes nodes={block.caption} path={`${key}-caption`} />
              ) : undefined
            }
            {...(block.floatHint === undefined ? {} : { floatHint: block.floatHint })}
            {...(block.widthHint === undefined ? {} : { widthHint: block.widthHint })}
            key={`${key}-${block.asset.assetId}`}
          />
        )
      case 'subpart':
        return (
          <div className="vmsh-subpart" key={key}>
            <div className="vmsh-subpart-header">
              <strong className="vmsh-subpart-label">{block.label})</strong>
              {problem ? renderSubpartActions?.(problem, block.label) : null}
            </div>
            <div className="vmsh-subpart-content">
              <ContentBlocks
                blocks={block.blocks}
                path={`${key}-blocks`}
                {...(problem === undefined ? {} : { problem })}
                {...(renderAfterSubpart === undefined ? {} : { renderAfterSubpart })}
                {...(renderSubpartActions === undefined ? {} : { renderSubpartActions })}
              />
            </div>
            {problem ? renderAfterSubpart?.(problem, block.label) : null}
          </div>
        )
      case 'callout':
        return (
          <aside className={`vmsh-callout vmsh-callout-${block.kind}`} key={key}>
            {block.title ? <strong className="vmsh-note-title">{block.title}</strong> : null}
            <ContentBlocks
              blocks={block.blocks}
              path={`${key}-blocks`}
              {...(problem === undefined ? {} : { problem })}
              {...(renderAfterSubpart === undefined ? {} : { renderAfterSubpart })}
              {...(renderSubpartActions === undefined ? {} : { renderSubpartActions })}
            />
          </aside>
        )
      case 'divider':
        return <hr key={key} />
    }
  })
}
/* eslint-enable jsx-a11y/no-noninteractive-tabindex */

export interface SemanticMathDocumentProps {
  document: WebContentDocument
  className?: string
  renderAfterProblem?: (problem: WebContentProblem) => ReactNode
  renderAfterSubpart?: (problem: WebContentProblem, label: string) => ReactNode
  renderProblemActions?: (problem: WebContentProblem) => ReactNode
  renderSubpartActions?: (problem: WebContentProblem, label: string) => ReactNode
}

/** Renders only an already runtime-validated WebContentDocument v1. */
export function SemanticMathDocument({
  document,
  className,
  renderAfterProblem,
  renderAfterSubpart,
  renderProblemActions,
  renderSubpartActions,
}: SemanticMathDocumentProps) {
  return (
    <MathDocument
      {...(className === undefined ? {} : { className })}
      {...(document.title === null ? {} : { title: document.title })}
    >
      <ContentBlocks blocks={document.introduction} path="introduction" />
      {document.problems.map((problem) => {
        const headingId = `problem-${problem.ordinal}`
        return (
          <Fragment key={problem.ordinal}>
            <section aria-labelledby={headingId} className="vmsh-problem">
              <div className="vmsh-problem-header">
                <h2 id={headingId}>
                  {problem.sourceItem ?? `Задача ${problem.ordinal}`}
                  {problem.title ? <span>{problem.title}</span> : null}
                </h2>
                {renderProblemActions?.(problem)}
              </div>
              <ContentBlocks
                blocks={problem.blocks}
                path={`problem-${problem.ordinal}`}
                problem={problem}
                {...(renderAfterSubpart === undefined ? {} : { renderAfterSubpart })}
                {...(renderSubpartActions === undefined ? {} : { renderSubpartActions })}
              />
              {renderAfterProblem?.(problem)}
            </section>
            <ContentBlocks
              blocks={problem.trailingBlocks ?? []}
              path={`problem-${problem.ordinal}-trailing`}
            />
          </Fragment>
        )
      })}
    </MathDocument>
  )
}
