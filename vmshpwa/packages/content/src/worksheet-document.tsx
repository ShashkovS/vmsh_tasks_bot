import { SemanticMathDocument, type SemanticMathDocumentProps } from './math-document'

/** Student paper geometry also used by Staff preview; docs/worksheet-materials.md. */
export function WorksheetDocument(props: SemanticMathDocumentProps) {
  return (
    <SemanticMathDocument
      {...props}
      imageLoading="eager"
      className="vmsh-student-feed-sheet px-5 py-6 sm:px-10 sm:py-8"
    />
  )
}
