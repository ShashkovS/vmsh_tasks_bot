import type {
  AccountProvisioningPreviewResponse,
  AccountProvisioningReceipt,
} from '@vmsh/contracts'

const APPLY_CHUNK_SIZE = 20

type ReceiptRow = AccountProvisioningReceipt['rows'][number]

/**
 * Keep expensive Argon2 work below the reverse-proxy timeout and preserve a
 * row-level receipt. See development-plan/05-phase-1-auth.md.
 */
export async function applyProvisioningInChunks<Row>({
  rows,
  initialPreview,
  preview,
  apply,
  onProgress,
  onChunkCompleted,
}: {
  rows: Row[]
  initialPreview: AccountProvisioningPreviewResponse
  preview: (rows: Row[]) => Promise<AccountProvisioningPreviewResponse>
  apply: (
    rows: Row[],
    preview: AccountProvisioningPreviewResponse,
  ) => Promise<AccountProvisioningReceipt>
  onProgress?: ((processed: number, total: number) => void) | undefined
  onChunkCompleted?: ((rows: ReceiptRow[]) => void) | undefined
}): Promise<AccountProvisioningReceipt> {
  const readyRowNumbers: number[] = []
  const receiptRows: ReceiptRow[] = []
  const seen = new Set<number>()

  for (const row of initialPreview.rows) {
    if (row.rowNumber > rows.length || seen.has(row.rowNumber)) {
      throw new Error('Некорректная нумерация строк в предпросмотре')
    }
    seen.add(row.rowNumber)
    if (row.state === 'ready') readyRowNumbers.push(row.rowNumber)
    else receiptRows.push({ rowNumber: row.rowNumber, state: 'skipped', code: row.code })
  }
  if (seen.size !== rows.length) throw new Error('Предпросмотр вернул не все строки')

  let processed = receiptRows.length
  onProgress?.(processed, rows.length)
  const requestIds: string[] = []
  for (let offset = 0; offset < readyRowNumbers.length; offset += APPLY_CHUNK_SIZE) {
    const sourceNumbers = readyRowNumbers.slice(offset, offset + APPLY_CHUNK_SIZE)
    const sourceRows = sourceNumbers.map((rowNumber) => rows[rowNumber - 1]!)
    // Refresh each small preview immediately before apply. This keeps its CAS
    // useful even when an earlier chunk has just claimed a duplicate login.
    const currentPreview = await preview(sourceRows)
    const receipt = await apply(sourceRows, currentPreview)
    requestIds.push(receipt.requestId)
    const completedRows: ReceiptRow[] = []
    for (const result of receipt.rows) {
      const originalRowNumber = sourceNumbers[result.rowNumber - 1]
      if (originalRowNumber === undefined) {
        throw new Error('Некорректная нумерация строк в результате импорта')
      }
      const mapped = { ...result, rowNumber: originalRowNumber }
      receiptRows.push(mapped)
      completedRows.push(mapped)
    }
    onChunkCompleted?.(completedRows)
    processed += sourceRows.length
    onProgress?.(processed, rows.length)
  }

  receiptRows.sort((left, right) => left.rowNumber - right.rowNumber)
  const created = receiptRows.filter((row) => row.state === 'created').length
  return {
    schemaVersion: 1,
    counts: { total: rows.length, created, skipped: rows.length - created },
    rows: receiptRows,
    requestId: requestIds.at(-1) ?? initialPreview.requestId,
  }
}
