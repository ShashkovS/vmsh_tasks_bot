import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { PageStatePanel } from './page-layout'
import {
  ServiceAvailabilityBannerView,
  connectionFailureText,
  useBrowserOnline,
} from './service-availability'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

// docs/service-failure-copy-20261004.md: never blame a user's internet for a server failure.
it.each([false, true])(
  'explains a confirmed server failure, including prolonged recovery: %s',
  (prolonged) => {
    render(
      <ServiceAvailabilityBannerView
        state={{ state: 'reconnecting', cause: 'server', since: 1, prolonged }}
      />,
    )
    const status = screen.getByRole('status')
    expect(status.textContent).toContain('Сервис временно недоступен')
    expect(status.textContent).toContain('Проблема на нашей стороне')
    expect(status.textContent).toContain('Проверяем доступность автоматически')
    expect(status.textContent).not.toContain('Проверьте интернет')
  },
)

it('uses neutral wording when an unsuccessful fetch has no confirmed cause', () => {
  render(
    <ServiceAvailabilityBannerView
      state={{ state: 'reconnecting', cause: 'unknown', since: 1, prolonged: false }}
    />,
  )
  expect(screen.getByRole('status').textContent).toContain('Сервер не отвечает')
  expect(screen.getByRole('status').textContent).not.toContain('Нет подключения к интернету')
  expect(screen.getByRole('status').textContent).not.toContain('Проблема на нашей стороне')
})

it('updates the connection explanation when the browser goes offline and returns online', () => {
  function Notice() {
    return <p>{connectionFailureText(useBrowserOnline())}</p>
  }
  vi.stubGlobal('navigator', { onLine: true })
  render(<Notice />)
  expect(screen.getByText('Не получили ответ от сервера. Попробуйте позже.')).toBeTruthy()
  vi.stubGlobal('navigator', { onLine: false })
  fireEvent(window, new Event('offline'))
  expect(
    screen.getByText('Нет подключения к интернету. Повторите попытку, когда связь появится.'),
  ).toBeTruthy()
  vi.stubGlobal('navigator', { onLine: true })
  fireEvent(window, new Event('online'))
  expect(
    screen.queryByText('Нет подключения к интернету. Повторите попытку, когда связь появится.'),
  ).toBeNull()
})

it.each([true, false])(
  'does not call a failed page read an internet outage unless the browser is offline: %s',
  (online) => {
    vi.stubGlobal('navigator', { onLine: online })
    render(<PageStatePanel state="offline" />)
    expect(screen.getByRole('heading').textContent).toBe(
      online ? 'Сервер не отвечает' : 'Нет подключения к интернету',
    )
  },
)
