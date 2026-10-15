import type { Backtest, Evidence } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatCount, formatSkillIndex } from '@/lib/format'

const PRODUCT_NAME: Record<Evidence['product'], string> = {
  aqi_1h: 'AQI +1h · rule-based',
  aqi_6h: 'AQI +6h · model',
  aqi_24h: 'AQI +24h · experimental',
  pm25_1h: 'PM2.5 +1h · model',
  pm25_6h: 'PM2.5 +6h · model',
  pm25_24h: 'PM2.5 +24h',
}

function withInterval(value: number | null, lo: number | null, hi: number | null): string {
  if (value === null) return '—'
  const interval = lo === null || hi === null ? '' : ` [${formatSkillIndex(lo)}, ${formatSkillIndex(hi)}]`
  return `${formatSkillIndex(value)}${interval}`
}

/** What each published product scored, on the held-out winter and on the Sep–Oct 2026 replay, with intervals. */
export function EvidenceTable({ backtest }: { backtest: Backtest }) {
  return (
    <Card as="section" aria-labelledby="evidence-title" className="flex w-full flex-col gap-3 px-5 py-6 md:px-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="evidence-title" className="text-17 font-semibold">
          How good are these forecasts?
        </h2>
        <span className="text-13 text-ink-muted">Skill: 0 = no better than assuming nothing changes; 1 = perfect</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-14">
          <thead>
            <tr className="text-left text-13 text-ink-muted">
              <th scope="col" className="py-2.5 pr-3 font-medium">Product</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Window</th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">Hours scored</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Skill vs same-as-now</th>
              <th scope="col" className="py-2.5 pl-3 font-medium">Skill vs 24h-window update</th>
            </tr>
          </thead>
          <tbody>
            {backtest.evidence.map((e) => (
              <tr key={`${e.product}-${e.window}`} className="border-t border-line-soft">
                <th scope="row" className="py-3 pr-3 text-left font-medium">{PRODUCT_NAME[e.product]}</th>
                <td className="px-3 py-3 text-ink-2">{e.window}</td>
                <td className="px-3 py-3 text-right font-mono">{e.n === null ? '—' : formatCount(e.n)}</td>
                <td className="px-3 py-3 font-mono">
                  {withInterval(e.skillVsPersistence, e.skillVsPersistenceLo, e.skillVsPersistenceHi)}
                </td>
                <td className="py-3 pl-3 font-mono">
                  {withInterval(e.skillVsWindowUpdate, e.skillVsWindowUpdateLo, e.skillVsWindowUpdateHi)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-13 text-ink-muted">{backtest.note}</p>
    </Card>
  )
}
