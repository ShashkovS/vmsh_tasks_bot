import { t } from '@lingui/core/macro'
import { ApiResponseError } from '@vmsh/contracts'

export function describeReviewError(error: unknown): string {
  if (error instanceof ApiResponseError) {
    if (error.code === 'review_already_claimed')
      return t`Эту работу уже проверяет другой преподаватель. Обновите очередь.`
    if (error.code === 'review_lease_lost')
      return t`Срок блокировки работы истёк. Откройте работу заново и повторите проверку.`
    if (error.code === 'review_thread_changed')
      return t`Пока вы проверяли, школьник дополнил работу. Откройте её заново перед сохранением.`
    if (error.status === 404) return t`Работа уже исчезла из очереди или была проверена.`
    return t`${error.message} Код обращения: ${error.requestId}.`
  }
  return t`Нет связи с сервером или получен неожиданный ответ. Повторите действие.`
}
