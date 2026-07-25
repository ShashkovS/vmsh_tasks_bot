import { useId, useState } from 'react'

import { Input, Label, RadioGroup, RadioGroupItem, cn } from '@vmsh/ui'

import {
  answerInputKind,
  answerInputMode,
  defaultAnswerHint,
  parseListAnswer,
  resolveArity,
  type AnswerSpec,
} from './answer-spec'
import { parseLegacyAnswerItems, validateAnswerFormat } from './answer-validation'

/*
 * Test-answer input. One component covers every ANS_TYPE by collapsing them to
 * four affordances (scalar / fixed tuple / comma list / single choice). It is
 * uncontrolled inside and reports the normalized answer string through
 * `onChange`; the page decides what to do with it. A plain-Russian format hint
 * with an example is always shown.
 */
export interface TestAnswerProps {
  spec: AnswerSpec
  /** Field label, e.g. «Ответ». */
  label?: string | undefined
  defaultValue?: string | undefined
  onChange?: ((value: string) => void) | undefined
  name?: string | undefined
  disabled?: boolean | undefined
  invalid?: boolean | undefined
  className?: string | undefined
}

export function TestAnswer({
  spec,
  label = 'Ответ',
  defaultValue = '',
  onChange,
  name,
  disabled,
  invalid,
  className,
}: TestAnswerProps) {
  const kind = answerInputKind(spec.type)
  const arity = resolveArity(spec)
  const fallback = defaultAnswerHint(spec.type)
  const hint = spec.hint ?? fallback.hint
  const example = spec.example ?? fallback.example

  const fieldId = useId()
  const labelId = useId()
  const hintId = useId()
  const errorId = useId()

  const [text, setText] = useState(defaultValue)
  const [parts, setParts] = useState<string[]>(() => {
    const seed = parseListAnswer(defaultValue)
    return Array.from({ length: arity }, (_, index) => seed[index] ?? '')
  })

  const emitText = (value: string) => {
    setText(value)
    onChange?.(value)
  }

  const emitPart = (index: number, value: string) => {
    const next = parts.map((part, current) => (current === index ? value : part))
    setParts(next)
    onChange?.(next.map((part) => part.trim()).join(', '))
  }

  const currentValue = kind === 'tuple' ? parts.map((part) => part.trim()).join(', ') : text
  const hasInput = kind === 'tuple' ? parts.some((part) => part.trim() !== '') : text.trim() !== ''
  const formatInvalid = invalid ?? (hasInput && !validateAnswerFormat(spec, currentValue))
  const parsedItems =
    kind === 'list' && !formatInvalid ? parseLegacyAnswerItems(spec.type, text) : []
  const describedBy = formatInvalid ? `${hintId} ${errorId}` : hintId

  return (
    <div className={cn('space-y-1.5', className)}>
      <span className="block text-label font-medium text-foreground" id={labelId}>
        {label}
      </span>

      {kind === 'scalar' ? (
        <Input
          aria-describedby={describedBy}
          aria-invalid={formatInvalid || undefined}
          aria-labelledby={labelId}
          disabled={disabled}
          id={fieldId}
          inputMode={answerInputMode(spec.type)}
          name={name}
          onChange={(event) => emitText(event.target.value)}
          placeholder={example || undefined}
          value={text}
        />
      ) : null}

      {kind === 'list' ? (
        <div className="space-y-1.5">
          <Input
            aria-describedby={describedBy}
            aria-invalid={formatInvalid || undefined}
            aria-labelledby={labelId}
            disabled={disabled}
            id={fieldId}
            inputMode="text"
            name={name}
            onChange={(event) => emitText(event.target.value)}
            placeholder={example || undefined}
            value={text}
          />
          {parsedItems.length > 0 ? (
            <div className="flex flex-wrap items-center gap-1" role="status">
              <span className="text-caption text-muted-foreground">Распознано:</span>
              {parsedItems.map((item, index) => (
                <span
                  className="rounded bg-surface-subtle px-1.5 py-0.5 font-num text-caption text-muted-foreground"
                  key={`${index}-${item}`}
                >
                  {item}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {kind === 'tuple' ? (
        <div
          aria-describedby={describedBy}
          aria-labelledby={labelId}
          className="flex flex-wrap gap-2"
          role="group"
        >
          {parts.map((part, index) => (
            <Input
              aria-label={`Число ${index + 1}`}
              aria-invalid={formatInvalid || undefined}
              className="w-16 text-center"
              disabled={disabled}
              inputMode="numeric"
              key={index}
              onChange={(event) => emitPart(index, event.target.value)}
              value={part}
            />
          ))}
        </div>
      ) : null}

      {kind === 'choice' ? (
        <RadioGroup
          aria-describedby={describedBy}
          aria-labelledby={labelId}
          disabled={disabled}
          onValueChange={(value) => emitText(String(value))}
          value={text}
        >
          {(spec.options ?? []).map((option) => (
            <div className="flex items-center gap-2" key={option.value}>
              <RadioGroupItem id={`${fieldId}-${option.value}`} value={option.label} />
              <Label className="font-normal" htmlFor={`${fieldId}-${option.value}`}>
                {option.label}
              </Label>
            </div>
          ))}
        </RadioGroup>
      ) : null}

      <p className="text-caption text-muted-foreground" id={hintId}>
        {hint}
        {example ? <span> · например {example}</span> : null}
      </p>
      {formatInvalid ? (
        <p className="text-caption font-medium text-status-danger" id={errorId} role="alert">
          {spec.validationError ??
            `Ответ не соответствует формату: ${hint.toLocaleLowerCase('ru')}.`}
        </p>
      ) : null}
    </div>
  )
}
