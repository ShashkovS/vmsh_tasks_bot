import { i18n } from '@lingui/core'
import { msg, t } from '@lingui/core/macro'
import type { MetadataColumn } from '@vmsh/product'

// P6: UI labels resolve lazily; TSV values retain the existing Russian protocol.
// See dev/development-plan/24-i18n-execution-plan.md and MetadataGrid clipboard helpers.
export const problemTypeOptions = [
  {
    value: '1',
    get label() {
      return t`Тестовая`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardLabel: 'Тестовая',
  },
  {
    value: '2',
    get label() {
      return t`Письменная`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardLabel: 'Письменная',
  },
  {
    value: '3',
    get label() {
      return t`Устная`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardLabel: 'Устная',
  },
]

/* eslint-disable lingui/no-unlocalized-strings -- Stable Russian TSV labels accompany localized UI descriptors. */
const answerTypeDescriptors = [
  [1, msg`Цифра`, 'Цифра'],
  [2, msg`Натуральное число`, 'Натуральное число'],
  [3, msg`Целое число`, 'Целое число'],
  [4, msg`Отношение`, 'Отношение'],
  [5, msg`Десятичная дробь`, 'Десятичная дробь'],
  [6, msg`Обыкновенная или десятичная дробь`, 'Обыкновенная или десятичная дробь'],
  [7, msg`Последовательность целых`, 'Последовательность целых'],
  [8, msg`Два целых`, 'Два целых'],
  [9, msg`Три целых`, 'Три целых'],
  [10, msg`Четыре целых`, 'Четыре целых'],
  [11, msg`Множество целых`, 'Множество целых'],
  [12, msg`Многочлен`, 'Многочлен'],
  [13, msg`Число с точностью`, 'Число с точностью'],
  [14, msg`Время`, 'Время'],
  [15, msg`Дата`, 'Дата'],
  [16, msg`День недели`, 'День недели'],
  [17, msg`Последовательность дробей`, 'Последовательность дробей'],
  [18, msg`Мультимножество`, 'Мультимножество'],
  [19, msg`Смешанная дробь`, 'Смешанная дробь'],
  [20, msg`Символьное выражение`, 'Символьное выражение'],
  [21, msg`Эквивалентное выражение`, 'Эквивалентное выражение'],
  [98, msg`Выбор одного варианта`, 'Выбор одного варианта'],
  [99, msg`Строка`, 'Строка'],
] as const
/* eslint-enable lingui/no-unlocalized-strings */
export const answerTypeOptions = answerTypeDescriptors.map(([value, label, clipboardLabel]) => ({
  value: String(value),
  clipboardLabel,
  get label() {
    return i18n._(label)
  },
}))

export const metadataColumns: MetadataColumn[] = [
  {
    id: 'displayNumber',
    get header() {
      return t`Номер`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Номер',
    width: 80,
    minWidth: 64,
  },
  {
    id: 'title',
    get header() {
      return t`Название`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Название',
    width: 240,
    minWidth: 160,
  },
  {
    id: 'problemType',
    get header() {
      return t`Тип задачи`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Тип задачи',
    editor: 'select',
    width: 150,
    minWidth: 120,
    options: problemTypeOptions,
  },
  {
    id: 'answerType',
    get header() {
      return t`Тип ответа`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Тип ответа',
    editor: 'select',
    width: 210,
    minWidth: 160,
    options: answerTypeOptions,
  },
  {
    id: 'correctAnswer',
    get header() {
      return t`Правильный ответ`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Правильный ответ',
    editor: 'textarea',
    width: 180,
    minWidth: 120,
  },
  {
    id: 'answerValidation',
    get header() {
      return t`Своя валидация`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Своя валидация',
    editor: 'textarea',
    width: 240,
    minWidth: 160,
  },
  {
    id: 'validationError',
    get header() {
      return t`Ошибка формата`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Ошибка формата',
    editor: 'textarea',
    width: 260,
    minWidth: 160,
  },
  {
    id: 'correctAnswerChecker',
    get header() {
      return t`Проверяльщик`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Проверяльщик',
    editor: 'textarea',
    width: 240,
    minWidth: 160,
  },
  {
    id: 'wrongAnswer',
    get header() {
      return t`Неверный ответ`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Неверный ответ',
    editor: 'textarea',
    width: 240,
    minWidth: 160,
  },
  {
    id: 'congratulation',
    get header() {
      return t`Верный ответ`
    },
    // eslint-disable-next-line lingui/no-unlocalized-strings -- Stable TSV exchange value; P6 preserves clipboard compatibility.
    clipboardHeader: 'Верный ответ',
    editor: 'textarea',
    width: 240,
    minWidth: 160,
  },
]
