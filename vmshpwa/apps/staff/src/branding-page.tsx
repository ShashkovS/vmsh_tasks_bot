import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMutation, useQuery } from '@tanstack/react-query'
import { LOCALE_NATIVE_NAMES } from '@vmsh/i18n'
import { useState } from 'react'
import { fetchBranding, PageLayout, useAuthenticatedPrincipal } from '@vmsh/app-shell'
import {
  brandAssetBase,
  brandProfiles,
  brandingSelectionSchema,
  type BrandingSelection,
} from '@vmsh/contracts'
import { BrandIdentityProvider, Button, Card, CardContent, Sign179, Wordmark } from '@vmsh/ui'

/** Instance-wide administrator setting; docs/branding.md and branding_routes.py. */
export function BrandingPage() {
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff' || principal.role !== 'admin') {
    return (
      <PageLayout title={t`Оформление`}>
        <p role="alert">
          <Trans>Изменять оформление может только администратор</Trans>
        </p>
      </PageLayout>
    )
  }
  return <BrandingSettings />
}

function BrandingSettings() {
  const query = useQuery({
    queryKey: ['instance-branding'],
    queryFn: ({ signal }) => fetchBranding('staff', signal),
  })
  const mutation = useMutation({
    mutationFn: async (selection: BrandingSelection) => {
      const response = await fetch('/staff/api/v1/branding', {
        method: 'PUT',
        credentials: 'same-origin',
        redirect: 'error',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(selection),
      })
      if (response.status === 409) throw new Error(t`Оформление уже изменено. Обновите страницу.`)
      if (!response.ok) throw new Error(t`Не удалось сохранить оформление. Попробуйте снова.`)
      return brandingSelectionSchema.parse(await response.json())
    },
    onSuccess: () => window.location.reload(),
  })
  return (
    <PageLayout title={t`Оформление`}>
      {query.isPending ? (
        <p role="status">
          <Trans>Загрузка…</Trans>
        </p>
      ) : query.isError ? (
        <div role="alert">
          <p>
            <Trans>Не удалось загрузить оформление.</Trans>
          </p>
          <Button onClick={() => void query.refetch()}>
            <Trans>Повторить</Trans>
          </Button>
        </div>
      ) : (
        <BrandingSettingsView
          current={query.data}
          saving={mutation.isPending}
          error={mutation.error?.message}
          onSave={(selection) => mutation.mutate(selection)}
        />
      )}
    </PageLayout>
  )
}

export function BrandingSettingsView({
  current,
  saving,
  error,
  onSave,
}: {
  current: BrandingSelection
  saving: boolean
  error?: string | undefined
  onSave: (selection: BrandingSelection) => void
}) {
  const [selected, setSelected] = useState(current.profileId)
  return (
    <div className="max-w-3xl space-y-6">
      <p>
        <Trans>
          Оформление применяется ко всем кабинетам этого проекта после обновления страницы.
          Выбранный пользователем язык сохраняется.
        </Trans>
      </p>
      <fieldset disabled={saving} className="space-y-3">
        <legend className="mb-3 font-medium">
          <Trans>Профиль оформления</Trans>
        </legend>
        {brandProfiles.map((profile) => (
          <label key={profile.id} htmlFor={`brand-${profile.id}`} className="block cursor-pointer">
            <span className="sr-only">{profile.name}</span>
            <Card data-brand={profile.id} className="brand-preview">
              <CardContent className="flex flex-wrap items-center gap-4 p-4">
                <input
                  id={`brand-${profile.id}`}
                  type="radio"
                  name="brand"
                  value={profile.id}
                  checked={selected === profile.id}
                  onChange={() => setSelected(profile.id)}
                  aria-label={profile.name}
                />
                <BrandIdentityProvider
                  identity={{
                    name: profile.name,
                    logoUrl:
                      profile.id === 'vmsh'
                        ? undefined
                        : `${brandAssetBase(profile, 'staff')}icon.svg`,
                  }}
                >
                  <Sign179 size={48} />
                  <Wordmark size={22} />
                </BrandIdentityProvider>
                <span className="ml-auto text-sm text-muted-foreground">
                  {LOCALE_NATIVE_NAMES[profile.defaultLocale]}
                </span>
              </CardContent>
            </Card>
          </label>
        ))}
      </fieldset>
      {error ? (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      ) : null}
      <Button
        disabled={saving || selected === current.profileId}
        onClick={() => onSave({ profileId: selected, version: current.version })}
      >
        {saving ? <Trans>Сохраняем…</Trans> : <Trans>Применить</Trans>}
      </Button>
    </div>
  )
}
