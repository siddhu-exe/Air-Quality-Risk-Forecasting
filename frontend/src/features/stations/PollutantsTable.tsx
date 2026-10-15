import type { Pollutant } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { POLLUTANTS } from '@/lib/pollutants'

const concentration = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })

/** Each pollutant's latest hourly concentration; an empty list says the station has no recent reading. */
export function PollutantsTable({ pollutants }: { pollutants: readonly Pollutant[] }) {
  return (
    <Card as="section" aria-labelledby="pollutants-title" className="min-w-0 flex-[999_1_560px] px-5 py-6 md:px-7">
      <h2 id="pollutants-title" className="mb-3 text-17 font-semibold">
        Pollutants now
      </h2>
      {pollutants.length === 0 ? (
        <p className="text-ink-2">No recent pollutant readings for this station.</p>
      ) : (
        <table className="w-full border-collapse text-14">
          <thead>
            <tr className="text-left text-13 text-ink-muted">
              <th scope="col" className="py-2 font-medium">
                Pollutant
              </th>
              <th scope="col" className="py-2 text-right font-medium">
                Concentration
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
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      <p className="mt-3 text-13 text-ink-muted">AQI is the highest pollutant sub-index, averaged over 24 hours (CPCB method).</p>
    </Card>
  )
}
