import { Link } from 'react-router-dom'
import type { GrapAlerts } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { categoryOf, formatAqi } from '@/lib/aqi'

type Row = GrapAlerts['stations'][number]

const stageText = (stage: Row['stageNow']): string => (stage ? `Stage ${stage}` : 'Below Stage I')

function Value({ value, stage }: { value: number | null; stage: Row['stageNow'] }) {
  if (value === null) return <span className="text-13 text-ink-muted">— no value</span>
  return (
    <span className="flex flex-col">
      <span className="font-mono font-medium">{formatAqi(value)}</span>
      <span className="text-12 text-ink-muted">
        {categoryOf(value).label} · {stageText(stage)}
      </span>
    </span>
  )
}

function Experimental({ row }: { row: Row }) {
  if (row.forecast24h === null) return <span className="text-13 text-ink-muted">— no forecast</span>
  return (
    <span className="flex flex-col">
      <span className="font-mono font-medium">{formatAqi(row.forecast24h)}</span>
      <span className="text-12 text-ink-muted">
        same as now: {row.persistence === null ? '—' : formatAqi(row.persistence)}
      </span>
    </span>
  )
}

/** Each station now, in six hours (model) and in 24 hours (experimental, beside plain persistence). */
export function GrapStations({ stations }: { stations: GrapAlerts['stations'] }) {
  return (
    <Card as="section" aria-labelledby="grap-stations-title" className="flex flex-col gap-3 px-5 py-6 md:px-7">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="grap-stations-title" className="text-17 font-semibold">
          Stations against the stage bands
        </h2>
        <span className="text-13 text-ink-muted">A dash means there is no value, not that it is low</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-14">
          <thead>
            <tr className="text-left text-13 text-ink-muted">
              <th scope="col" className="py-2.5 pr-3 font-medium">Station</th>
              <th scope="col" className="px-3 py-2.5 font-medium">Now</th>
              <th scope="col" className="px-3 py-2.5 font-medium">In 6 hours · model</th>
              <th scope="col" className="py-2.5 pl-3 font-medium">In 24 hours · experimental</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((row) => (
              <tr key={row.stationId} className="border-t border-line-soft align-top">
                <th scope="row" className="py-3 pr-3 text-left font-medium">
                  <Link to={`/stations/${row.stationId}`} className="text-ink">
                    {row.name}
                  </Link>
                </th>
                <td className="px-3 py-3">
                  <Value value={row.now} stage={row.stageNow} />
                </td>
                <td className="px-3 py-3">
                  <Value value={row.forecast6h} stage={row.stage6h} />
                </td>
                <td className="py-3 pl-3">
                  <Experimental row={row} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
