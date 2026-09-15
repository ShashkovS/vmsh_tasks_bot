import { ApiResponseError } from '@vmsh/contracts'

export function describeReviewError(error: unknown): string {
  if (error instanceof ApiResponseError) {
    if (error.code === 'review_already_claimed')
      return 'Эту работу уже проверяет другой преподаватель. Обновите очередь.'
    if (error.code === 'review_lease_lost')
      return 'Срок блокировки работы истёк. Откройте работу заново и повторите проверку.'
    if (error.code === 'review_thread_changed')
      return 'Пока вы проверяли, школьник дополнил работу. Откройте её заново перед сохранением.'
    if (error.status === 404) return 'Работа уже исчезла из очереди или была проверена.'
    return `${error.message} Код обращения: ${error.requestId}.`
  }
  return 'Нет связи с сервером или получен неожиданный ответ. Повторите действие.'
}
