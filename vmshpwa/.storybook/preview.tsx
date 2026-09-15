import type { Decorator, Preview } from '@storybook/react-vite'
import { initialize, mswLoader } from 'msw-storybook-addon'

import { AppProviders } from '@vmsh/app-shell'
import '@vmsh/ui/styles.css'

initialize({
  onUnhandledRequest(request, print) {
    if (/\/(student|family|staff)\/api\//.test(new URL(request.url).pathname)) {
      print.error()
    }
  },
})

type Globals = { theme?: unknown; density?: unknown; motion?: unknown }

const withTheme: Decorator = (Story, context) => {
  const globals = context.globals as Globals
  const theme = globals.theme === 'dark' ? 'dark' : 'light'
  const density = typeof globals.density === 'string' ? globals.density : 'student'
  const reducedMotion = globals.motion === 'reduce'

  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.style.colorScheme = theme
  root.dataset.density = density
  if (reducedMotion) root.dataset.motion = 'reduce'
  else delete root.dataset.motion

  // Stories that paint their own full-bleed surface opt out of the canvas padding.
  const padded = (context.parameters as { canvasPadding?: boolean }).canvasPadding !== false

  return (
    <AppProviders>
      <div className={padded ? 'min-h-svh bg-background p-6 text-foreground' : 'min-h-svh'}>
        <Story />
      </div>
    </AppProviders>
  )
}

const preview: Preview = {
  decorators: [withTheme],
  loaders: [mswLoader],
  globalTypes: {
    theme: {
      description: 'Цветовая тема',
      defaultValue: 'light',
      toolbar: {
        icon: 'paintbrush',
        items: [
          { value: 'light', title: 'Светлая' },
          { value: 'dark', title: 'Тёмная' },
        ],
      },
    },
    density: {
      description: 'Плотность интерфейса',
      defaultValue: 'student',
      toolbar: {
        icon: 'component',
        items: [
          { value: 'student', title: 'Школьник' },
          { value: 'family', title: 'Семья' },
          { value: 'staff', title: 'Учитель и администратор' },
        ],
      },
    },
    motion: {
      description: 'Анимация',
      defaultValue: 'default',
      toolbar: {
        icon: 'play',
        items: [
          { value: 'default', title: 'Обычная' },
          { value: 'reduce', title: 'Уменьшенная' },
        ],
      },
    },
  },
  parameters: {
    layout: 'fullscreen',
    controls: { expanded: true },
    a11y: { test: 'error' },
    options: {
      storySort: { order: ['Foundations', 'UI', 'Product', 'Pages', 'Exploration'] },
    },
  },
}

export default preview
