import { messages as brandingMessages } from '@vmsh/branding/locales/ru.po'
import { messages as ui } from '@vmsh/ui/locales/ru.po'

import { messages as landing } from '../locales/ru.po'

/** Russian catalog of the Landing app and every `@vmsh/*` package it uses. */
export const messages = {
  ...brandingMessages,
  ...ui,
  ...landing,
}
