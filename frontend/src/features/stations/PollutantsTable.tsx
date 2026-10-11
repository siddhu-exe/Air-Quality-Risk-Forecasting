import type { Pollutant } from '@/api/schemas'
import { TIER_FILL } from '@/components/aqi/tierClasses'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { AQI_SCALE_MAX, categoryOf } from '@/lib/aqi'
import { POLLUTANTS } from '@/lib/pollutants'

const concentration = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })

/** Each pollutant's concentration and its CPCB sub-index; the AQI is the highest sub-index. */
export function PollutantsTable({ pollutants }: { pollutants: readonly Pollutant[] }) {
  return (
    <Card as="section" aria-labelledby="pollutants-title" className="min-w-0 flex-[999_1_560px] px-7 py-6">
      <h2 id="pollutants-title" className="mb-3 text-17 font-semibold">
        Pollutants now
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-14">
          <thead>
            <tr className="text-left text-13 text-ink-muted">
              <th scope="col" className="py-2 font-medium">
                Pollutant
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                Concentration
              </th>
              <th scope="col" className="py-2 pl-6 font-medium">
                Sub-index
              </th>
            </tr>
          </thead>
          <tbody>
            {pollutants.map((pollutant) => {
              const info = POLLUTANTS[pollutant.key]
              return (
                <tr key={pollutant.key} className="border-t border-line-soft">
                  <th scope="row" className="py-3 text-left font-medium">
                    {info.label} {info.tag && <span className="font-normal text-ink-muted">{info.tag}</span>}
                  </th>
                  <td className="py-3 text-right font-mono">
                    {concentration.format(pollutant.concentration)}{' '}
                    <span className="text-ink-muted">{pollutant.unit}</span>
                  </td>
                  <td className="py-3 pl-6">
                    <span className="flex items-center gap-2.5">
                      <ProgressBar
                        value={pollutant.subIndex / AQI_SCALE_MAX}
                        fillClassName={`h-full ${TIER_FILL[categoryOf(pollutant.subIndex).key]}`}
                        className="max-w-[220px] flex-1"
                      />
                      <span className="w-8 text-right font-mono">{Math.round(pollutant.subIndex)}</span>
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-13 text-ink-muted">AQI is the highest sub-index, averaged over 24 hours (CPCB method).</p>
    </Card>
  )
}
