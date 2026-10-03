import { cleanup } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { DistributionViolin } from './progress-charts'

afterEach(cleanup)

it('keeps the silhouette within observed scores on a shared axis and outside the label gutter', () => {
  const { container } = render(
    <DistributionViolin values={[2, 3, 4]} domain={[0, 15]} height={260} bandwidth={0.5} />,
  )
  const path = container.querySelector('path')!.getAttribute('d')!
  const coordinates = [...path.matchAll(/[ML] ([\d.-]+) ([\d.-]+)/g)].map((m) => [
    Number(m[1]),
    Number(m[2]),
  ])
  expect(Math.min(...coordinates.map((p) => p[0]!))).toBeGreaterThanOrEqual(36)
  expect(Math.max(...coordinates.map((p) => p[0]!))).toBeLessThanOrEqual(208)
  expect(Math.min(...coordinates.map((p) => p[1]!))).toBeCloseTo(248 - (4 / 15) * 236, 0)
  expect(Math.max(...coordinates.map((p) => p[1]!))).toBeCloseTo(248 - (2 / 15) * 236, 0)
})

it('retains two peaks separated by an empty interval', () => {
  const { container } = render(
    <DistributionViolin values={[0, 0, 0, 10, 10, 10]} domain={[0, 10]} bandwidth={0.5} />,
  )
  const points = [
    ...container
      .querySelector('path')!
      .getAttribute('d')!
      .matchAll(/[ML] ([\d.-]+) ([\d.-]+)/g),
  ]
  const middle = points.filter((p) => Math.abs(Number(p[2]) - 100) < 2)
  expect(middle.length).toBeGreaterThan(0)
  for (const point of middle) expect(Number(point[1])).toBeCloseTo(122, 0)
  const median = container.querySelector('svg > line')!
  expect(
    Number(median.getAttribute('x2')) - Number(median.getAttribute('x1')),
  ).toBeGreaterThanOrEqual(20)
})

it.each([[3], [3, 3, 3], [0, 0]])(
  'does not invent density for constant samples %j',
  (...values) => {
    const { container } = render(<DistributionViolin values={values} domain={[0, 15]} />)
    expect(container.querySelector('path')).toBeNull()
    expect(container.innerHTML).not.toMatch(/NaN|Infinity/)
  },
)

it('calculates fractional quartiles from observations, not density samples', () => {
  const { getByRole, container } = render(
    <DistributionViolin values={[0, 0.5, 1, 1.5, 2]} domain={[0, 3]} />,
  )
  expect(getByRole('img').getAttribute('aria-label')).toContain(
    'Медиана 1.0, разброс от 0.5 до 1.5',
  )
  const box = container.querySelector('rect')!
  expect(Number(box.getAttribute('y'))).toBeCloseTo(100)
  expect(Number(box.getAttribute('height'))).toBeCloseTo(176 / 3)
})

it('does not render invalid SVG for empty data', () => {
  const { container } = render(<DistributionViolin values={[]} />)
  expect(container.querySelector('svg')).toBeNull()
})
