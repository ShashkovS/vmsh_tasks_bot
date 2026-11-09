import { useCallback, useState } from 'react'

import type { GroupBanner, PrincipalQueryScope } from '@vmsh/contracts'

function key(principal: PrincipalQueryScope): string {
  return `vmshpwa:${principal.audience}:${principal.accountId}:dismissed-banners`
}

export function readDismissedBanners(
  storage: Pick<Storage, 'getItem'>,
  principal: PrincipalQueryScope,
): ReadonlySet<string> {
  try {
    const value: unknown = JSON.parse(storage.getItem(key(principal)) ?? '[]')
    if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) return new Set()
    return new Set(value)
  } catch {
    return new Set()
  }
}

export function bannerDismissalId(banner: GroupBanner): string {
  return `${banner.bannerId}:v${banner.version}`
}

export function writeDismissedBanner(
  storage: Pick<Storage, 'getItem' | 'setItem'>,
  principal: PrincipalQueryScope,
  banner: GroupBanner,
): ReadonlySet<string> {
  const dismissed = new Set(readDismissedBanners(storage, principal))
  dismissed.add(bannerDismissalId(banner))
  storage.setItem(key(principal), JSON.stringify([...dismissed]))
  return dismissed
}

export function useBannerDismissals(principal: PrincipalQueryScope) {
  const [dismissed, setDismissed] = useState<ReadonlySet<string>>(() =>
    readDismissedBanners(globalThis.localStorage, principal),
  )
  const dismiss = useCallback(
    (banner: GroupBanner) => {
      setDismissed(writeDismissedBanner(globalThis.localStorage, principal, banner))
    },
    [principal],
  )
  return { dismissed, dismiss }
}
