import { messages as appShell } from '@vmsh/app-shell/locales/en.po'
import { messages as content } from '@vmsh/content/locales/en.po'
import { messages as product } from '@vmsh/product/locales/en.po'
import { messages as ui } from '@vmsh/ui/locales/en.po'

import { messages as staff } from '../locales/en.po'

/** English catalog of the Staff app and every `@vmsh/*` package it uses. */
export const messages = { ...ui, ...content, ...product, ...appShell, ...staff }
