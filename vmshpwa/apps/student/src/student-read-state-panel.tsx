import { t } from '@lingui/core/macro'
import type { ComponentProps } from 'react'
import { PageStatePanel } from '@vmsh/app-shell'

export function StudentReadStatePanel(props: ComponentProps<typeof PageStatePanel>) {
  return (
    <PageStatePanel
      {...props}
      {...(props.state === 'offline'
        ? {
            title: t`Материал ещё не сохранён на устройстве`,
            description: t`Подключитесь к интернету, чтобы загрузить этот материал.`,
          }
        : {})}
    />
  )
}
