import { useId } from 'react'
import type { MonthlyFlow } from '../services/dashboard'

import { formatMoney, monthLabel } from '../utils/format'

function axisMoney(value: number) {
  return new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

export function ChartLegend({ budget = false }: { budget?: boolean }) {
  return <div className="chart-legend" aria-label="Legenda">
    <span><i className="legend-primary" />{budget ? 'Previsto' : 'Receitas'}</span>
    <span><i className="legend-secondary" />{budget ? 'Realizado' : 'Despesas'}</span>
  </div>
}

export function MonthlyChart({ data }: { data: MonthlyFlow[] }) {
  const id = useId()
  const width = 1000, height = 300, left = 68, right = 30, top = 20, bottom = 52
  const maximum = Math.max(...data.flatMap((item) => [Number(item.income), Number(item.expenses)]), 1)
  const x = (i: number) => left + (i / Math.max(data.length - 1, 1)) * (width - left - right)
  const y = (v: string) => top + (1 - Number(v) / maximum) * (height - top - bottom)
  return <div className="chart-scroll"><svg className="monthly-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={id}>
    <title id={id}>Evolução mensal de receitas e despesas em reais. Valores exatos na tabela de dados.</title>
    {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
      const axisY = top + (1 - fraction) * (height - top - bottom)
      return <g key={fraction}><line className="chart-grid" x1={left} x2={width - right} y1={axisY} y2={axisY} />
        <text className="axis-label" x={left - 12} y={axisY + 4} textAnchor="end">{axisMoney(maximum * fraction)}</text></g>
    })}
    {(['income', 'expenses'] as const).map((key, index) => <g key={key} className={index === 0 ? 'series-primary' : 'series-secondary'}>
      <polyline className="chart-line" strokeDasharray={index === 1 ? '7 5' : undefined} points={data.map((row, i) => `${x(i)},${y(row[key])}`).join(' ')} />
      {data.map((row, i) => <circle key={`${row.year}-${row.month}`} cx={x(i)} cy={y(row[key])} r={4} tabIndex={0}
        aria-label={`${monthLabel(row.year, row.month)}: ${key === 'income' ? 'receitas' : 'despesas'} ${formatMoney(row[key])}`}>
        <title>{`${monthLabel(row.year, row.month)} · ${key === 'income' ? 'Receitas' : 'Despesas'}: ${formatMoney(row[key])}`}</title>
      </circle>)}
    </g>)}
    {data.map((row, i) => <text key={`${row.year}-${row.month}`} className="axis-label" x={x(i)} y={height - 20} textAnchor="middle">{monthLabel(row.year, row.month)}</text>)}
  </svg></div>
}

export type BarRow = { id: string; label: string; first: string; second?: string; note?: string }

export function HorizontalBars({ rows, firstLabel, secondLabel }: {
  rows: BarRow[]; firstLabel: string; secondLabel?: string
}) {
  const maximum = Math.max(...rows.flatMap((row) => [Number(row.first), Number(row.second ?? '0')]), 1)
  return <div className="bar-chart" role="list" aria-label="Comparação em reais, com escala comum">
    {rows.map((row) => <div className="bar-row" role="listitem" key={row.id}>
      <div className="bar-label"><strong>{row.label}</strong>{row.note && <span>{row.note}</span>}</div>
      <div className="bar-series">
        <div className="bar-value-row"><div className="bar-track" aria-hidden="true"><div className="bar-fill primary" style={{ width: `${Number(row.first) / maximum * 100}%` }} /></div>
          <span><span className="sr-only">{firstLabel}: </span>{formatMoney(row.first)}</span></div>
        {row.second !== undefined && <div className="bar-value-row"><div className="bar-track" aria-hidden="true"><div className="bar-fill secondary" style={{ width: `${Number(row.second) / maximum * 100}%` }} /></div>
          <span><span className="sr-only">{secondLabel}: </span>{formatMoney(row.second)}</span></div>}
      </div>
    </div>)}
  </div>
}
