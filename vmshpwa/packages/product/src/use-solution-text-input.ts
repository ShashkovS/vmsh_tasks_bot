import { useRef, type ClipboardEvent, type FormEvent, type KeyboardEvent } from 'react'
import { solutionTextEdit, type SolutionTextEdit } from '@vmsh/contracts'

/** docs/paste-evidence.md: one provenance update per actual textarea change. */
export function useSolutionTextInput(
  onChange: (value: string, edit?: SolutionTextEdit) => void,
  onPaste?: (count: number) => void,
) {
  const pending = useRef<SolutionTextEdit | undefined>(undefined)
  return {
    onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
      pending.current = solutionTextEdit(event.currentTarget)
    },
    onPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
      const count = event.clipboardData.getData('text').length
      pending.current = {
        ...solutionTextEdit(event.currentTarget),
        pasted: count > 0,
        pastedCharacterCount: count,
      }
    },
    onBeforeInput(event: FormEvent<HTMLTextAreaElement>) {
      const inputType = (event.nativeEvent as InputEvent).inputType
      const paste = pending.current?.pasted && (!inputType || inputType === 'insertFromPaste')
      pending.current = {
        ...solutionTextEdit(event.currentTarget, inputType),
        ...(paste ? pending.current : {}),
        inputType,
      }
    },
    onChange() {},
    onInput(event: FormEvent<HTMLTextAreaElement>) {
      const inputType = (event.nativeEvent as InputEvent).inputType
      const edit = pending.current
      pending.current = undefined
      const actualType = inputType ?? edit?.inputType
      const actualEdit = {
        ...(edit ?? solutionTextEdit(event.currentTarget)),
        inputType: actualType,
        pasted: actualType ? actualType === 'insertFromPaste' : edit?.pasted,
      }
      if (actualEdit?.pasted && actualEdit.pastedCharacterCount)
        onPaste?.(actualEdit.pastedCharacterCount)
      onChange(event.currentTarget.value, actualEdit)
    },
    onBlur() {
      pending.current = undefined
    },
  }
}
