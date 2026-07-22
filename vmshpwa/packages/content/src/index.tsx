import type { ReactNode } from 'react'

export interface MathDocumentProps {
  title?: string
  children: ReactNode
  className?: string
}

export function MathDocument({ title, children, className }: MathDocumentProps) {
  return (
    <article className={className} data-slot="math-document">
      {title ? <h1 className="mb-4 font-reading text-2xl font-semibold">{title}</h1> : null}
      <div className="font-reading text-[1.05rem] leading-8">{children}</div>
    </article>
  )
}

export interface ContentArtifact {
  source: 'latex'
  sourceVersion: string
  html: string
  assetIds: string[]
  generatedAt: string
}
