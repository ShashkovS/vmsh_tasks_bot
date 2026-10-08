import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Check, Languages } from 'lucide-react'
import { useCallback, useState } from 'react'

import type { InterfaceLocale } from '@vmsh/contracts'
import { LOCALE_NATIVE_NAMES, SUPPORTED_LOCALES, useLocale, writeLocaleCookie } from '@vmsh/i18n'
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  FieldLabel,
  RadioGroup,
  RadioGroupItem,
} from '@vmsh/ui'

import { useAuthentication } from './auth-context'

export interface InterfaceLanguageController {
  locale: InterfaceLocale
  saving: boolean
  failed: boolean
  select: (locale: InterfaceLocale) => Promise<void>
}

/**
 * Saves the account language, then reloads so every screen, cached formatter
 * and service-worker page renders in it (docs/i18n.md, «Переключение языка»).
 */
export function useInterfaceLanguage(): InterfaceLanguageController {
  const authentication = useAuthentication()
  const { locale } = useLocale()
  const [saving, setSaving] = useState(false)
  const [failed, setFailed] = useState(false)

  const select = useCallback(
    async (next: InterfaceLocale) => {
      if (next === locale || saving) return
      setSaving(true)
      setFailed(false)
      try {
        await authentication.client.updateLocale(next)
        writeLocaleCookie(next)
        window.location.reload()
      } catch (error) {
        authentication.handleApiError(error)
        setFailed(true)
        setSaving(false)
      }
    },
    [authentication, locale, saving],
  )

  return { locale, saving, failed, select }
}

function isInterfaceLocale(value: unknown): value is InterfaceLocale {
  return (SUPPORTED_LOCALES as readonly unknown[]).includes(value)
}

/** Profile card of Student and Family (the personal cabinet). */
export function InterfaceLanguageCard() {
  const language = useInterfaceLanguage()
  return (
    <Card>
      <CardHeader>
        <CardTitle id="interface-language-title">
          <Trans>Язык интерфейса</Trans>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-small text-muted-foreground">
          <Trans>
            Язык сохраняется в учётной записи и применяется на всех ваших устройствах. Условия задач
            и новости остаются на языке оригинала.
          </Trans>
        </p>
        <RadioGroup
          aria-labelledby="interface-language-title"
          disabled={language.saving}
          onValueChange={(value) => {
            if (isInterfaceLocale(value)) void language.select(value)
          }}
          value={language.locale}
        >
          {SUPPORTED_LOCALES.map((locale) => (
            <div className="flex min-h-10 items-center gap-3" key={locale}>
              <RadioGroupItem id={`interface-language-${locale}`} value={locale} />
              <FieldLabel htmlFor={`interface-language-${locale}`} lang={locale}>
                {LOCALE_NATIVE_NAMES[locale]}
              </FieldLabel>
            </div>
          ))}
        </RadioGroup>
        {language.saving ? (
          <p className="text-small text-muted-foreground" role="status">
            <Trans>Сохраняем…</Trans>
          </p>
        ) : null}
        {language.failed ? (
          <p className="text-small text-status-error" role="alert">
            <Trans>Не удалось сохранить язык. Проверьте подключение и попробуйте ещё раз.</Trans>
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

/** Compact header menu for Staff, which has no personal cabinet page. */
export function InterfaceLanguageMenu() {
  const language = useInterfaceLanguage()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            aria-label={t`Язык интерфейса`}
            disabled={language.saving}
            size="icon-sm"
            title={t`Язык интерфейса`}
            variant="ghost"
          >
            <Languages aria-hidden="true" />
          </Button>
        }
      />
      <DropdownMenuContent align="end">
        {SUPPORTED_LOCALES.map((locale) => (
          <DropdownMenuItem key={locale} onClick={() => void language.select(locale)}>
            <span className="flex-1" lang={locale}>
              {LOCALE_NATIVE_NAMES[locale]}
            </span>
            {language.locale === locale ? <Check aria-hidden="true" /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
