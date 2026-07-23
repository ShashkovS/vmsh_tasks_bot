import type { Meta, StoryObj } from '@storybook/react-vite'

import { IconFamily, IconStaff, IconStudent, Sign179, Wordmark } from './marks'

function BrandSheet() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-1 text-foreground">
      <header>
        <p className="text-label font-medium tracking-wide text-primary uppercase">
          ВМШ 179 · направление B
        </p>
        <h1 className="text-display font-semibold">Знак, логотип и продуктовые иконки</h1>
      </header>

      <section className="space-y-3">
        <h2 className="text-section font-semibold">Знак «179» на разных размерах</h2>
        <div className="flex flex-wrap items-end gap-6 text-primary">
          {[192, 48, 32, 24, 16].map((s) => (
            <div key={s} className="space-y-1 text-center">
              <Sign179 size={s} />
              <p className="text-caption text-muted-foreground">{s}px</p>
            </div>
          ))}
        </div>
        <p className="text-small text-muted-foreground">
          Наследует <code className="font-mono">currentColor</code> — monochrome, печать и обе темы
          из одного asset.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-section font-semibold">Логотип</h2>
        <div className="flex flex-wrap items-center gap-8">
          <Wordmark size={28} className="text-foreground" />
          <span className="inline-flex items-center gap-2 text-primary">
            <Sign179 size={28} />
            <Wordmark size={22} className="text-foreground" />
          </span>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-section font-semibold">Продуктовые иконки</h2>
        <p className="text-label text-muted-foreground">
          Семья со знаком, но не заменяют подпись роли.
        </p>
        <div className="flex flex-wrap gap-6">
          {[
            { Icon: IconStudent, label: 'Школьник' },
            { Icon: IconFamily, label: 'Семья' },
            { Icon: IconStaff, label: 'Учитель' },
          ].map(({ Icon, label }) => (
            <span
              key={label}
              className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-body"
            >
              <Icon size={24} />
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-section font-semibold">Монохром на поверхностях</h2>
        <div className="flex flex-wrap gap-4">
          <span className="grid size-16 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Sign179 size={34} />
          </span>
          <span className="grid size-16 place-items-center rounded-lg bg-surface text-foreground shadow-e2">
            <Sign179 size={34} />
          </span>
          <span className="grid size-16 place-items-center rounded-lg bg-foreground text-background">
            <Sign179 size={34} />
          </span>
        </div>
      </section>
    </div>
  )
}

const meta = { title: 'Foundations/Brand', component: BrandSheet } satisfies Meta<typeof BrandSheet>
export default meta
type Story = StoryObj<typeof meta>

export const Light: Story = { globals: { theme: 'light' } }
export const Dark: Story = { globals: { theme: 'dark' } }
