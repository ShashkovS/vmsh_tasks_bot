import { ApiResponseError } from '@vmsh/contracts'

export function describeReviewError(error: unknown): string {
  if (error instanceof ApiResponseError) {
    if (error.status === 409)
      return 'Эту работу уже проверяет другой преподаватель. Обновите очередь.'
    if (error.status === 404) return 'Работа уже исчезла из очереди или была проверена.'
    return `${error.message} Код обращения: ${error.requestId}.`
  }
  return 'Нет связи с сервером или получен неожиданный ответ. Повторите действие.'
}
