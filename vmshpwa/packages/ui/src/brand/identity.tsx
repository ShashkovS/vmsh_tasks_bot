import { createContext, useContext, type ReactNode } from 'react'

export interface BrandIdentity {
  name: string
  supportEmail?: string
  logoUrl?: string | undefined
}
// eslint-disable-next-line lingui/no-unlocalized-strings -- repository brand name; runtime provider supplies the localized identity
const BrandContext = createContext<BrandIdentity>({ name: 'ВМШ 179' })

/** Repository profile composition is owned by app-shell; see docs/branding.md. */
export function BrandIdentityProvider({
  identity,
  children,
}: {
  identity: BrandIdentity
  children: ReactNode
}) {
  return <BrandContext.Provider value={identity}>{children}</BrandContext.Provider>
}
export function useBrandIdentity(): BrandIdentity & { supportEmail: string } {
  const identity = useContext(BrandContext)
  return { ...identity, supportEmail: identity.supportEmail ?? 'vmsh@179.ru' }
}
