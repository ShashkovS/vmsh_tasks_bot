import { Clock3 } from 'lucide-react'

import { submissionDeadlineMessage } from '@vmsh/app-shell'
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

export function StudentSubmissionDeadlineNotice() {
  return (
    <Alert role="status" tone="warning">
      <Clock3 aria-hidden="true" />
      <AlertContent>
        <AlertTitle>Приём завершён</AlertTitle>
        <AlertDescription>{submissionDeadlineMessage()}</AlertDescription>
      </AlertContent>
    </Alert>
  )
}
