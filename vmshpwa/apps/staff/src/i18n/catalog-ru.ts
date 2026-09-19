import { messages as appShell } from '@vmsh/app-shell/locales/ru.po'
import { messages as content } from '@vmsh/content/locales/ru.po'
import { messages as product } from '@vmsh/product/locales/ru.po'
import { messages as ui } from '@vmsh/ui/locales/ru.po'

import { messages as staff } from '../locales/ru.po'

/** Russian catalog of the Staff app and every `@vmsh/*` package it uses. */
export const messages = { ...ui, ...content, ...product, ...appShell, ...staff }
