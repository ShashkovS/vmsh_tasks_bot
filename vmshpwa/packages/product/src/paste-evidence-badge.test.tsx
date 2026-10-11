import { afterEach, expect, it } from 'vitest'
import { cleanup, fireEvent, screen } from '@testing-library/react'
import { renderWithI18n } from '@vmsh/test-utils/i18n'
import { TooltipProvider } from '@vmsh/ui'
import { PasteEvidenceBadge } from './paste-evidence-badge'

afterEach(cleanup)

it('hides unknown/zero estimates and explains the historical method on click', async () => {
  renderWithI18n(
    <TooltipProvider>
      <PasteEvidenceBadge estimate={null} />
      <PasteEvidenceBadge estimate={{ percentage: 0, method: 'remaining_text' }} />
      <PasteEvidenceBadge estimate={{ percentage: 42, method: 'cumulative_pastes' }} />
    </TooltipProvider>,
  )
  expect(screen.getAllByRole('button')).toHaveLength(1)
  expect(screen.getByText('Вставлено ≈ 42%')).toBeTruthy()
  fireEvent.click(screen.getByRole('button'))
  expect((await screen.findByRole('tooltip')).textContent).toContain(
    'не учитывает последующие удаления',
  )
})
