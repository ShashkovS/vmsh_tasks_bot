import { z } from 'zod'
import profiles from './brand-profiles.json' with { type: 'json' }

// Shared with helpers/pwa/branding.py; see docs/branding.md.
export const brandIdSchema = z.enum(['vmsh', 'tlf-prep-clubs'])
export const brandProfileSchema = z.object({
  id: brandIdSchema,
  name: z.string().min(1),
  englishName: z.string().min(1),
  supportEmail: z.email(),
  defaultLocale: z.enum(['ru', 'en']),
  assetVersion: z.number().int().positive(),
  themeColor: z.string().regex(/^#[0-9a-f]{6}$/i),
  backgroundColor: z.string().regex(/^#[0-9a-f]{6}$/i),
})
export const brandProfiles = z.array(brandProfileSchema).parse(profiles)
export type BrandProfile = z.infer<typeof brandProfileSchema>
export const brandingSelectionSchema = z.object({
  profileId: brandIdSchema,
  version: z.number().int().positive(),
})
export type BrandingSelection = z.infer<typeof brandingSelectionSchema>
export function brandProfile(id: BrandingSelection['profileId']): BrandProfile {
  return brandProfiles.find((profile) => profile.id === id)!
}
export function brandAssetBase(profile: BrandProfile, audience: string): string {
  return profile.id === 'vmsh'
    ? `/${audience}/`
    : `/${audience}/brands/${profile.id}/v${profile.assetVersion}/`
}

/** Only public identity is stored here, never authenticated API responses. */
export function brandingCacheName(audience: string): string {
  return `vmsh-${audience}-branding-v1`
}
