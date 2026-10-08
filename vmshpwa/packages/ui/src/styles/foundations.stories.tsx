import type { Meta, StoryObj } from '@storybook/react-vite'

/*
 * Foundations — Phase 2 token review surface (art direction B).
 * Uses ONLY semantic token utilities; no raw colours. Class names are written
 * in full because Tailwind cannot see interpolated strings. The Signals section
 * is the gate artefact proving level ≠ status ≠ verdict and human ≠ AI.
 */

function Section({
  title,
  note,
  children,
}: {
  title: string
  note?: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="border-b border-border pb-1">
        <h2 className="text-section font-semibold">{title}</h2>
        {note ? <p className="text-label text-muted-foreground">{note}</p> : null}
      </div>
      {children}
    </section>
  )
}

function Swatch({ className, name, fg }: { className: string; name: string; fg?: string }) {
  return (
    <div className="space-y-1">
      <div className={`flex h-14 items-end rounded-md border border-border p-1.5 ${className}`}>
        {fg ? <span className={`text-label font-medium ${fg}`}>Аа Яя 179</span> : null}
      </div>
      <p className="text-caption text-muted-foreground">{name}</p>
    </div>
  )
}

/** Accepted level chip: neutral surface + letter; level hue only as a quiet marker. */
const levels = [
  { code: 'н', name: 'Начинающие', marker: 'border-level-1-border text-level-1' },
  { code: 'п', name: 'Продолжающие', marker: 'border-level-2-border text-level-2' },
  { code: 'х', name: 'Эксперты', marker: 'border-level-3-border text-level-3' },
  { code: 'т', name: 'Тестирование', marker: 'border-level-0-border text-level-0' },
]

function LevelChip({ code, name, marker }: { code: string; name: string; marker: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1 text-label font-medium text-foreground">
      <span
        aria-hidden="true"
        className={`grid size-4 place-items-center rounded-sm border text-caption font-semibold ${marker}`}
      >
        {code}
      </span>
      {name}
    </span>
  )
}

const verdicts = [
  {
    sym: '−',
    label: 'Отклонено',
    chip: 'bg-verdict-negative-surface text-verdict-negative border-verdict-negative',
  },
  {
    sym: '−.',
    label: 'Есть простая идея',
    chip: 'bg-verdict-partial-low-surface text-verdict-partial-low border-verdict-partial-low',
  },
  {
    sym: '∓',
    label: 'Есть идеи, не доведено',
    chip: 'bg-verdict-partial-low-surface text-verdict-partial-low border-verdict-partial-low',
  },
  {
    sym: '+/2',
    label: 'Половина',
    chip: 'bg-verdict-partial-mid-surface text-verdict-partial-mid border-verdict-partial-mid',
  },
  {
    sym: '±',
    label: 'В целом верно',
    chip: 'bg-verdict-partial-high-surface text-verdict-partial-high border-verdict-partial-high',
  },
  {
    sym: '+.',
    label: 'Зачтено с недочётами',
    chip: 'bg-verdict-positive-surface text-verdict-positive border-verdict-positive',
  },
  {
    sym: '+',
    label: 'Зачтено',
    chip: 'bg-verdict-positive-surface text-verdict-positive border-verdict-positive',
  },
]

const statusesSurface = [
  {
    label: 'Зачтено',
    chip: 'bg-status-success-surface text-status-success border-status-success-border',
  },
  {
    label: 'Нужна доработка',
    chip: 'bg-status-warning-surface text-status-warning border-status-warning-border',
  },
  {
    label: 'Ошибка отправки',
    chip: 'bg-status-danger-surface text-status-danger border-status-danger-border',
  },
  {
    label: 'На проверке',
    chip: 'bg-status-info-surface text-status-info border-status-info-border',
  },
]

const statusesSolid = [
  { label: 'Зачтено', chip: 'bg-status-success text-status-success-foreground' },
  { label: 'Нужна доработка', chip: 'bg-status-warning text-status-warning-foreground' },
  { label: 'Ошибка отправки', chip: 'bg-status-danger text-status-danger-foreground' },
  { label: 'На проверке', chip: 'bg-status-info text-status-info-foreground' },
]

const radii = [
  { name: 'rounded-sm', cls: 'rounded-sm' },
  { name: 'rounded-md', cls: 'rounded-md' },
  { name: 'rounded-lg', cls: 'rounded-lg' },
  { name: 'rounded-xl', cls: 'rounded-xl' },
]
const shadows = [
  { name: 'shadow-e1', cls: 'shadow-e1' },
  { name: 'shadow-e2', cls: 'shadow-e2' },
  { name: 'shadow-e3', cls: 'shadow-e3' },
  { name: 'shadow-e4', cls: 'shadow-e4' },
]

function Foundations() {
  return (
    <div className="mx-auto max-w-4xl space-y-8 p-1">
      <header>
        <p className="text-label font-medium tracking-wide text-primary uppercase">
          ВМШ 179 · направление B
        </p>
        <h1 className="text-display font-semibold">Токены дизайн-системы</h1>
        <p className="mt-1 max-w-2xl text-small text-muted-foreground">
          Семантический слой. Продуктовый код использует только эти имена, не сырые цвета.
        </p>
      </header>

      <Section title="Поверхности и текст">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Swatch className="bg-background" name="background" fg="text-foreground" />
          <Swatch className="bg-surface" name="surface" fg="text-foreground" />
          <Swatch className="bg-surface-subtle" name="surface-subtle" fg="text-foreground" />
          <Swatch className="bg-surface-sunken" name="surface-sunken" fg="text-foreground" />
          <Swatch className="bg-muted" name="muted" fg="text-muted-foreground" />
          <Swatch className="bg-paper" name="paper (чтение)" fg="text-foreground" />
          <Swatch className="bg-primary" name="primary" fg="text-primary-foreground" />
          <Swatch className="bg-primary-soft" name="primary-soft" fg="text-accent-foreground" />
        </div>
        <p className="text-small text-foreground">
          Обычный текст · <span className="text-muted-foreground">приглушённый</span> ·{' '}
          <span className="text-foreground-subtle">третичный</span> ·{' '}
          <a className="text-link underline underline-offset-2" href="#foundations">
            ссылка
          </a>
        </p>
      </Section>

      <Section title="Статусы" note="Значение всегда несут символ и подпись, а не только цвет">
        <div className="flex flex-wrap gap-2">
          {statusesSurface.map((s) => (
            <span
              key={s.label}
              className={`inline-flex items-center rounded-md border px-2 py-1 text-label font-medium ${s.chip}`}
            >
              {s.label}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {statusesSolid.map((s) => (
            <span
              key={s.label}
              className={`inline-flex items-center rounded-md px-2 py-1 text-label font-medium ${s.chip}`}
            >
              {s.label}
            </span>
          ))}
        </div>
      </Section>

      <Section
        title="Независимость: уровень × статус × вердикт × автор"
        note="Уровень — категориальный, не оценка. Вердикт — оценка. Их нельзя перепутать."
      >
        <div className="flex flex-wrap items-center gap-2">
          {levels.map((level) => (
            <LevelChip key={level.code} {...level} />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {verdicts.map((verdict) => (
            <span
              key={verdict.sym + verdict.label}
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-label font-semibold ${verdict.chip}`}
            >
              <span aria-hidden="true" className="font-num">
                {verdict.sym}
              </span>
              {verdict.label}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-provenance-human-surface px-2 py-1 text-label text-foreground">
            Проверил преподаватель
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-provenance-ai-border bg-provenance-ai-surface px-2 py-1 text-label font-medium text-provenance-ai">
            <span aria-hidden="true">🤖</span> ИИ · не преподаватель
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-unread px-2 py-0.5 text-caption font-medium text-unread-foreground">
            новое
          </span>
        </div>
      </Section>

      <Section title="Типографика" note="IBM Plex Sans (интерфейс) · Source Serif 4 (чтение)">
        <p className="font-reading text-reading">
          Ладья бьёт по горизонтали или вертикали на любое количество клеток. Ёжик съел{' '}
          <span className="italic">четверть</span>, встречаются числа −7, 3×5 и 179.
        </p>
        <div className="space-y-1">
          <p className="text-display font-semibold">Display · заголовок</p>
          <p className="text-title font-semibold">Title · раздел</p>
          <p className="text-body">Body · основной интерфейсный текст 16px</p>
          <p className="text-small text-muted-foreground">Small · вторичный</p>
          <p className="font-num text-small tabular-nums">
            Цифры таблиц: 0123456789 · 16:30 · 131/203 · 21н.6
          </p>
        </div>
      </Section>

      <Section title="Радиус и тень">
        <div className="flex flex-wrap items-end gap-4">
          {radii.map((r) => (
            <div key={r.name} className="space-y-1 text-center">
              <div className={`size-12 border border-border bg-surface ${r.cls}`} />
              <p className="text-caption text-muted-foreground">{r.name}</p>
            </div>
          ))}
          {shadows.map((s) => (
            <div key={s.name} className="space-y-1 text-center">
              <div className={`size-12 rounded-md bg-surface ${s.cls}`} />
              <p className="text-caption text-muted-foreground">{s.name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Отступы и движение">
        <div className="space-y-1.5">
          {[
            { name: 'control-gap', v: 'var(--control-gap)' },
            { name: 'page-gutter', v: 'var(--page-gutter)' },
            { name: 'section-gap', v: 'var(--section-gap)' },
            { name: 'reading-indent', v: 'var(--reading-indent)' },
          ].map((sp) => (
            <div className="flex items-center gap-3" key={sp.name}>
              <div className="h-3 rounded-xs bg-primary-soft" style={{ width: sp.v }} />
              <span className="text-caption text-muted-foreground">{sp.name}</span>
            </div>
          ))}
        </div>
        <p className="text-small text-muted-foreground">
          Движение: <span className="font-num">fast 120ms</span> ·{' '}
          <span className="font-num">normal 190ms</span> ·{' '}
          <span className="font-num">slow 280ms</span>, easing standard. При{' '}
          <code className="font-mono text-caption">prefers-reduced-motion</code> переходы становятся
          мгновенными.
        </p>
      </Section>

      <Section
        title="Плотность: школьник ↔ учитель"
        note="Одна форма, разные плотности через data-density (primitives перейдут на эти токены в Phase 3)"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          {(['student', 'staff'] as const).map((density) => (
            <div className="space-y-2" data-density={density} key={density}>
              <p className="text-label font-medium">
                {density === 'student' ? 'Школьник (touch)' : 'Учитель (compact)'}
              </p>
              <div
                className="flex items-center rounded-md border border-border bg-surface px-3 text-small"
                style={{ minHeight: 'var(--touch-target)' }}
              >
                Поле ответа
              </div>
              <div
                className="flex items-center justify-center rounded-md bg-primary px-3 text-small font-medium text-primary-foreground"
                style={{ minHeight: 'var(--touch-target-primary)' }}
              >
                Отправить
              </div>
              <div className="overflow-hidden rounded-md border border-border">
                {['21н.1', '21н.6', '21н.8'].map((id) => (
                  <div
                    className="flex items-center border-b border-border px-3 text-small last:border-b-0"
                    key={id}
                    style={{ height: 'var(--row-height)' }}
                  >
                    <span className="font-num">{id}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}

const meta = { title: 'Foundations/Tokens', component: Foundations } satisfies Meta<
  typeof Foundations
>
export default meta
type Story = StoryObj<typeof meta>

export const Light: Story = { globals: { theme: 'light' } }
export const Dark: Story = { globals: { theme: 'dark' } }
export const StaffDensity: Story = {
  globals: { theme: 'light', density: 'staff' },
  name: 'Плотность Staff',
}
