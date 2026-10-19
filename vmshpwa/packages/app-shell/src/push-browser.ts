import {
  savePushSubscriptionRequestSchema,
  type SavePushSubscriptionRequest,
} from '@vmsh/contracts'

export function decodeApplicationServerKey(value: string): Uint8Array<ArrayBuffer> {
  const paddingLength = (4 - (value.length % 4)) % 4
  const padded = value.replaceAll('-', '+').replaceAll('_', '/') + '='.repeat(paddingLength)
  const bytes = atob(padded)
  return Uint8Array.from(bytes, (character) => character.charCodeAt(0))
}

export function browserPushSubscriptionRequest(
  subscription: PushSubscription,
): SavePushSubscriptionRequest {
  const value = subscription.toJSON()
  return savePushSubscriptionRequestSchema.parse({
    schemaVersion: 1,
    endpoint: value.endpoint,
    expirationTime: value.expirationTime ?? null,
    keys: value.keys,
  })
}
