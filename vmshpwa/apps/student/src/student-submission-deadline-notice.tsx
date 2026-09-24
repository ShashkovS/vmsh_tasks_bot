import { Trans } from '@lingui/react/macro'
import { Clock3 } from 'lucide-react'

import { submissionDeadlineMessage } from '@vmsh/app-shell'
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

export function StudentSubmissionDeadlineNotice() {
  return (
    <Alert role="status" tone="warning">
      <Clock3 aria-hidden="true" />
      <AlertContent>
        <AlertTitle>
          <Trans>Приём завершён</Trans>
        </AlertTitle>
        <AlertDescription>{submissionDeadlineMessage()}</AlertDescription>
      </AlertContent>
    </Alert>
  )
}
