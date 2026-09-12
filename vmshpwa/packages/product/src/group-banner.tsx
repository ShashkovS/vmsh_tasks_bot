import { X } from 'lucide-react'

import type { GroupBanner as GroupBannerView } from '@vmsh/contracts'
import { Alert, AlertContent, Button } from '@vmsh/ui'

import { RichDocumentView } from './rich-document'

export function GroupBanner({
  banner,
  onDismiss,
}: {
  banner: GroupBannerView
  onDismiss?: (() => void) | undefined
}) {
  return (
    <Alert className="border-accent/30 bg-accent/5" data-banner-id={banner.bannerId}>
      <AlertContent className="min-w-0">
        <p className="mb-1 text-caption text-muted-foreground">
          {banner.group.courseName} · {banner.group.name}
        </p>
        {banner.document ? (
          <RichDocumentView className="text-small" document={banner.document} />
        ) : (
          <div
            className="text-small [&_a]:text-link [&_a]:underline [&_code]:rounded [&_code]:bg-surface-sunken [&_code]:px-1"
            dangerouslySetInnerHTML={{ __html: banner.html }}
          />
        )}
      </AlertContent>
      {banner.dismissible && onDismiss ? (
        <Button aria-label="Скрыть объявление" onClick={onDismiss} size="icon-sm" variant="ghost">
          <X aria-hidden="true" />
        </Button>
      ) : null}
    </Alert>
  )
}
