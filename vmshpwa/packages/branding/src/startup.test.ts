import { afterEach, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { activateLocale } from '@vmsh/i18n'
import { allCatalogLoaders } from '../../../dev/test-support/i18n-catalogs'
import { renderBrandingWaiting } from './startup'

afterEach(() => document.body.replaceChildren())
it('keeps a prolonged update in a live waiting state without an error', () => {
  const root = document.createElement('div')
  document.body.append(root)
  renderBrandingWaiting(root, { state: 'updating', since: 1, prolonged: true })
  expect(screen.getByRole('heading', { name: 'Обновляем сервис' })).toBeTruthy()
  expect(screen.getByRole('status').textContent).toContain('Мы продолжаем подключаться.')
  expect(screen.queryByRole('alert')).toBeNull()
})
it('translates connection recovery using the activated device language', async () => {
  await activateLocale('en', allCatalogLoaders)
  const root = document.createElement('div')
  document.body.append(root)
  renderBrandingWaiting(root, { state: 'reconnecting', since: 1, prolonged: false })
  expect(screen.getByRole('heading', { name: 'Restoring the connection' })).toBeTruthy()
  expect(screen.getByRole('status').textContent).toContain('Your account will resume automatically')
})
