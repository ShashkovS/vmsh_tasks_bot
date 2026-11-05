import { t } from '@lingui/core/macro'
/*
 * Reaction registry (migrates the legacy numeric ids without losing meaning).
 * Reactions never replace a verdict or comment. Visibility is asymmetric and is
 * enforced as a permission state, not CSS: a student reaction is hidden from the
 * teacher (visible to admin); a teacher internal reaction is hidden from the
 * student/family (visible to admin). The oral stream mirrors the same rules.
 */
export type ReactionScope = 'student-written' | 'teacher-written' | 'student-oral' | 'teacher-oral'

export interface ReactionOption {
  id: number
  emoji: string
  label: string
  scope: ReactionScope
}

export const reactionRegistry: ReactionOption[] = [
  {
    id: 0,
    emoji: '👌',
    get label() {
      return t`Ок. Всё ясно.`
    },
    scope: 'student-written',
  },
  {
    id: 1,
    emoji: '😕',
    get label() {
      return t`Непонятно, что не так…`
    },
    scope: 'student-written',
  },
  {
    id: 2,
    emoji: '🙋',
    get label() {
      return t`Не могу согласиться с проверкой!`
    },
    scope: 'student-written',
  },
  {
    id: 100,
    emoji: '🔥',
    get label() {
      return t`Суперское решение.`
    },
    scope: 'teacher-written',
  },
  {
    id: 101,
    emoji: '😕',
    get label() {
      return t`Жуткая муть.`
    },
    scope: 'teacher-written',
  },
  {
    id: 102,
    emoji: '😠',
    get label() {
      return t`Решение, вероятно, списано.`
    },
    scope: 'teacher-written',
  },
  {
    id: 103,
    emoji: '🤖',
    get label() {
      return t`Решение, вероятно, от нейросети.`
    },
    scope: 'teacher-written',
  },
  {
    id: 200,
    emoji: '👌',
    get label() {
      return t`С устным приёмом всё ОК.`
    },
    scope: 'student-oral',
  },
  {
    id: 201,
    emoji: '😀',
    get label() {
      return t`Сдавать понравилось!`
    },
    scope: 'student-oral',
  },
  {
    id: 202,
    emoji: '📡',
    get label() {
      return t`Связь прервалась.`
    },
    scope: 'student-oral',
  },
  {
    id: 203,
    emoji: '😰',
    get label() {
      return t`Сдавать не понравилось…`
    },
    scope: 'student-oral',
  },
  {
    id: 204,
    emoji: '⌛',
    get label() {
      return t`Это старые плюсики поставили…`
    },
    scope: 'student-oral',
  },
  {
    id: 300,
    emoji: '👍',
    get label() {
      return t`Внятно, уверенно.`
    },
    scope: 'teacher-oral',
  },
  {
    id: 301,
    emoji: '👎',
    get label() {
      return t`Мутно, много ошибок.`
    },
    scope: 'teacher-oral',
  },
  {
    id: 302,
    emoji: '😠',
    get label() {
      return t`Решение, вероятно, несамостоятельно.`
    },
    scope: 'teacher-oral',
  },
  {
    id: 303,
    emoji: '📡',
    get label() {
      return t`Технические проблемы.`
    },
    scope: 'teacher-oral',
  },
]

/** Teacher scopes are internal — never present in a Student/Family view-model. */
export function isInternalReactionScope(scope: ReactionScope): boolean {
  return scope === 'teacher-written' || scope === 'teacher-oral'
}

export function reactionsForScope(scope: ReactionScope): ReactionOption[] {
  return reactionRegistry.filter((reaction) => reaction.scope === scope)
}

export function findReaction(id: number): ReactionOption | undefined {
  return reactionRegistry.find((reaction) => reaction.id === id)
}
