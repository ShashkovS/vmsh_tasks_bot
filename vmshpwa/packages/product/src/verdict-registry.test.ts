import { describe, expect, it } from 'vitest'

import { activateLocale } from '@vmsh/i18n'
import { allCatalogLoaders } from '../../../dev/test-support/i18n-catalogs'
import { writtenReviewVerdict } from './verdict-registry'

describe('written review verdict projection', () => {
  it.each([
    [11, 'rejected', '−'],
    [12, 'minus-dot', '−.'],
    [13, 'minus-plus', '∓'],
    [14, 'half', '+/2'],
    [15, 'plus-minus', '±'],
    [16, 'plus-dot', '+.'],
    [17, 'plus', '+'],
  ])('maps legacy code %s to %s', (code, value, symbol) => {
    expect(writtenReviewVerdict(code)).toMatchObject({ value, symbol, provenance: 'human' })
  })

  it('keeps AI provenance visibly distinct', () => {
    expect(writtenReviewVerdict(17, 'ai').provenance).toBe('ai')
  })

  it('does not freeze Russian verdict labels after the locale changes', async () => {
    await activateLocale('en', allCatalogLoaders)

    expect(writtenReviewVerdict(17)).toMatchObject({ label: 'Accepted' })
  })
})
