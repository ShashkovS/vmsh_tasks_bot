import { afterEach, describe, expect, it } from 'vitest'

import { activateLocale } from '@vmsh/i18n'

import { allCatalogLoaders } from '../../../dev/test-support/i18n-catalogs'
import { reviewReactionInboxLabel } from './review-reaction-inbox'

afterEach(async () => {
  await activateLocale('ru', allCatalogLoaders)
})

describe('review reaction inbox labels', () => {
  it('uses the stable reaction ID for a locale-aware label while preserving unknown history', async () => {
    await activateLocale('en', allCatalogLoaders)

    expect(reviewReactionInboxLabel(2, '🙋 Не могу согласиться с проверкой!')).toBe(
      '🙋 I disagree with the review!',
    )
    expect(reviewReactionInboxLabel(999, 'Сохранённая произвольная формулировка')).toBe(
      'Сохранённая произвольная формулировка',
    )
  })
})
