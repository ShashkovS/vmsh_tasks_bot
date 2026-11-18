import { i18n } from '@lingui/core'
import { expect, it } from 'vitest'
import { metadataColumns, answerTypeOptions } from './problem-metadata-columns'
import {
  matrixFromRows,
  normalizeClipboardValue,
} from '../../../packages/product/src/metadata-grid-clipboard'

// P6 acceptance: language activation changes labels, never TSV exchange values.
it('keeps Russian TSV headers and values across RU/EN activation', () => {
  const rows = [
    { displayNumber: '1', title: 'Авторская задача', problemType: '1', answerType: '2' },
  ]
  i18n.activate('ru')
  const russian = matrixFromRows(rows, metadataColumns, true)
  expect(answerTypeOptions.find((item) => item.value === '2')?.label).toBe('Натуральное число')
  i18n.activate('en')
  expect(metadataColumns[0]?.header).toBe('Number')
  expect(answerTypeOptions.find((item) => item.value === '2')?.label).toBe('Natural number')
  expect(matrixFromRows(rows, metadataColumns, true)).toEqual(russian)
  expect(normalizeClipboardValue('Натуральное число', metadataColumns[3]!)).toBe('2')
  expect(normalizeClipboardValue('Natural number', metadataColumns[3]!)).toBe('2')
  i18n.activate('ru')
  expect(metadataColumns[0]?.header).toBe('Номер')
})
