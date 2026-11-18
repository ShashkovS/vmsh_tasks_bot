import { describe, expect, it } from 'vitest'

import { activateLocale } from '@vmsh/i18n'
import { allCatalogLoaders } from '../../../dev/test-support/i18n-catalogs'
import { courseAchievementLabel } from './course-achievements'

describe('course achievement labels', () => {
  it('keeps Student and Family wording for the initial rules identical', () => {
    expect(courseAchievementLabel('first_submission')).toBe('Первая задача отправлена')
    expect(courseAchievementLabel('first_accepted')).toBe('Первая задача зачтена')
    expect(courseAchievementLabel('first_written_submission')).toBe('Первая письменная работа')
  })

  it('does not invent copy for a newer server rule', () => {
    expect(courseAchievementLabel('future_rule')).toBeUndefined()
  })

  it('resolves achievement labels after switching to English', async () => {
    await activateLocale('en', allCatalogLoaders)

    expect(courseAchievementLabel('first_submission')).toBe('First problem submitted')
    expect(courseAchievementLabel('first_accepted')).toBe('First problem accepted')
  })
})
