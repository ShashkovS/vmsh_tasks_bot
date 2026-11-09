import { t } from '@lingui/core/macro'
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
    // dev/ui-audit-20261104/BACKLOG.md 2.1: a banner reads as a card on the page grid, and
    // headings inside it do not outrank the page title.
    <Alert
      className="border-border border-l-4 border-l-accent bg-card shadow-xs"
      data-banner-id={banner.bannerId}
    >
      <AlertContent className="min-w-0">
        <p className="mb-1 text-caption text-muted-foreground">
          {banner.group.courseName} · {banner.group.name}
        </p>
        {banner.document ? (
          <RichDocumentView
            className="text-small [&_:is(h1,h2,h3)]:mt-0! [&_:is(h1,h2,h3)]:text-section!"
            document={banner.document}
          />
        ) : (
          <div
            className="text-small [&_a]:text-link [&_a]:underline [&_code]:rounded [&_code]:bg-surface-sunken [&_code]:px-1"
            dangerouslySetInnerHTML={{ __html: banner.html }}
          />
        )}
      </AlertContent>
      {banner.dismissible && onDismiss ? (
        <Button
          aria-label={t`Скрыть объявление`}
          onClick={onDismiss}
          size="icon-sm"
          variant="ghost"
        >
          <X aria-hidden="true" />
        </Button>
      ) : null}
    </Alert>
  )
}
