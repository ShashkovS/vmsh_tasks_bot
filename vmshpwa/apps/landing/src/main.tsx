import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@vmsh/ui/styles.css'

import { LandingPage } from './landing-page'

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element is missing')

createRoot(rootElement).render(
  <StrictMode>
    <LandingPage />
  </StrictMode>,
)
