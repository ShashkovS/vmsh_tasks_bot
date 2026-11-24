import { describe, expect, it } from 'vitest'

import { activateLocale } from '@vmsh/i18n'

import { allCatalogLoaders } from '../../../dev/test-support/i18n-catalogs'

import { testAttemptReply } from './student-test-answer-view'

describe('test attempt reply', () => {
  it('uses English product fallback wording while preserving checker feedback', async () => {
    await activateLocale('en', allCatalogLoaders)

    expect(testAttemptReply({ outcome: 'wrong', feedback: null, checkerMessage: null })).toBe(
      'The answer is not correct yet.',
    )
    expect(
      testAttemptReply({
        outcome: 'correct',
        feedback: 'Авторский текст преподавателя',
        checkerMessage: null,
      }),
    ).toBe('Авторский текст преподавателя')
  })
})
