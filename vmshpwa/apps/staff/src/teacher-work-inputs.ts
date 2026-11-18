import type { TeacherWorkInputs, TeacherWorkReceipt } from '@vmsh/contracts'

// docs/teacher-work.md: accepted writes avoid rereading the entire Zoom history.
export function acceptAliasReceipt(
  inputs: TeacherWorkInputs | undefined,
  receipt: TeacherWorkReceipt,
  submittedName: string,
): TeacherWorkInputs | undefined {
  if (!inputs || !receipt.alias) return inputs
  const accepted = receipt.alias
  return {
    ...inputs,
    signatures: inputs.signatures.map((signature) =>
      (signature.normalizedName === accepted.normalized_name || signature.name === submittedName) &&
      (signature.alias?.version ?? 0) <= accepted.version
        ? { ...signature, alias: accepted }
        : signature,
    ),
  }
}
