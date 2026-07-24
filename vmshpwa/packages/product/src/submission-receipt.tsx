import { CheckCircle2 } from 'lucide-react'

import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

/*
 * Server receipt after a submission. Shows the client and server times and a
 * stable reference (idempotency), so a duplicate retry is recognisable rather
 * than looking like a second submission.
 */
export interface SubmissionReceiptProps {
  clientTime: string
  serverTime?: string
  reference?: string
}

export function SubmissionReceipt({ clientTime, serverTime, reference }: SubmissionReceiptProps) {
  return (
    <Alert tone="success">
      <CheckCircle2 aria-hidden="true" />
      <AlertContent>
        <AlertTitle>Решение получено</AlertTitle>
        <AlertDescription>
          Отправлено {clientTime}
          {serverTime ? `, принято сервером ${serverTime}` : ''}.
          {reference ? ` Квитанция ${reference}.` : ''}
        </AlertDescription>
      </AlertContent>
    </Alert>
  )
}
