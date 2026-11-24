import { z } from 'zod'

/** docs/paste-evidence.md: packed UTF-16 provenance, low bit first. */
export const textOriginSchema = z
  .object({
    version: z.literal(1),
    utf16Length: z.number().int().min(0).max(100_000),
    bits: z
      .string()
      .max(16_668)
      .regex(/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/),
  })
  .strict()
  .superRefine((origin, context) => {
    let bytes: string
    try {
      bytes = atob(origin.bits)
    } catch {
      context.addIssue({ code: 'custom', message: 'Invalid text origin bit mask' })
      return
    }
    const remainder = origin.utf16Length % 8
    if (
      bytes.length !== Math.ceil(origin.utf16Length / 8) ||
      btoa(bytes) !== origin.bits ||
      (remainder > 0 && bytes.charCodeAt(bytes.length - 1) >> remainder !== 0)
    ) {
      context.addIssue({ code: 'custom', message: 'Invalid text origin bit mask' })
    }
  })
export type TextOrigin = z.infer<typeof textOriginSchema>

export const pasteEstimateSchema = z.object({
  percentage: z.number().int().min(0).max(100),
  method: z.enum(['remaining_text', 'cumulative_pastes']),
})
export type PasteEstimate = z.infer<typeof pasteEstimateSchema>

/** Input context only; clipboard contents never leave the solution field. */
export interface SolutionTextEdit {
  start: number
  end: number
  inputType?: string | undefined
  pasted?: boolean | undefined
  pastedCharacterCount?: number
}

export function solutionTextEdit(
  element: HTMLTextAreaElement,
  inputType?: string,
): SolutionTextEdit {
  return { start: element.selectionStart, end: element.selectionEnd, inputType }
}
