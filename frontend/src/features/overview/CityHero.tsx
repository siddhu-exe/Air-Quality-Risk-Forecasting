import { AqiScaleBar } from '@/components/aqi/AqiScaleBar'
import { CategoryPill } from '@/components/aqi/CategoryPill'
import { Card } from '@/components/ui/Card'
import { Eyebrow } from '@/components/ui/Eyebrow'
import type { Overview } from '@/api/schemas'
import { categoryOf, formatAqi } from '@/lib/aqi'
import { formatClock } from '@/lib/format'
import { outlook, type Outlook } from '@/lib/forecast'

interface CityHeroProps {
  overview: Overview
}

function Stat({ label, value, note, className }: { label: string; value: string; note: string; className?: string }) {
  return (
    <div className={className}>
      <p className="text-12 text-ink-muted md:text-13">{label}</p>
      <p className="mt-0.5 font-mono text-22 md:text-24">{value}</p>
      <p className="text-12 text-ink-muted">{note}</p>
    </div>
  )
}

const mean = (o: Outlook): string => (o.mean === null ? '—' : formatAqi(o.mean))
const coverage = (o: Outlook): string => (o.mean === null ? 'no station has one' : `${o.count} of ${o.total} stations`)

/** The headline: the city-average AQI right now, then the forecasts that exist, each with how many stations back it. */
export function CityHero({ overview }: CityHeroProps) {
  const { network, issuedAt, stations } = overview
  const now = network.meanAqiNow
  const oneHour = outlook(stations, 'aqi_1h')
  const sixHours = outlook(stations, 'aqi_6h')
  const scaleLabel =
    now === null
      ? 'No current AQI to place on the CPCB scale.'
      : `City average AQI ${formatAqi(now)} is ${categoryOf(now).label} on the CPCB scale of 0 to 500.`

  return (
    <Card
      as="section"
      aria-label="City now"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-3.5 p-[22px] md:gap-5 md:px-9 md:py-8"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <Eyebrow className="text-12 md:text-13">Right now · city average</Eyebrow>
        <p className="text-13 text-ink-muted">
          {network.stationsWithData} of {network.stationsTotal} stations reporting
          {issuedAt && <span className="hidden md:inline"> · forecasts issued {formatClock(issuedAt)} IST</span>}
        </p>
      </div>

      <div className="flex items-end gap-3.5 md:flex-wrap md:gap-x-7 md:gap-y-3">
        <h1 className="font-serif text-96 leading-[0.85] tracking-[-0.02em] md:text-136">
          <span className="sr-only">{now === null ? 'No current AQI' : 'City average AQI now '}</span>
          {now === null ? '—' : formatAqi(now)}
        </h1>
        <div className="flex flex-col gap-2 pb-1.5 md:pb-2">
          {now !== null && <CategoryPill aqi={now} size="md" className="self-start" />}
          <p className="max-w-[360px] text-ink-2">
            {now === null
              ? 'No station has a recent reading, so there is no current AQI to show.'
              : 'Mean of the stations with a recent reading; the CPCB AQI recomputed from live pollutants.'}
          </p>
        </div>
      </div>

      {now !== null && <AqiScaleBar thickness={10} now={now} forecast={sixHours.mean ?? now} label={scaleLabel} showAxis={false} className="md:hidden" />}
      {now !== null && <AqiScaleBar now={now} forecast={sixHours.mean ?? now} label={scaleLabel} className="hidden md:flex" />}

      <div className="grid grid-cols-1 gap-3 border-t border-line-soft pt-3 sm:grid-cols-2 md:grid-cols-3 md:gap-4 md:border-line md:pt-5">
        <Stat label="In 1 hour · rule-based" value={mean(oneHour)} note={coverage(oneHour)} />
        <Stat label="In 6 hours · model" value={mean(sixHours)} note={coverage(sixHours)} />
        <Stat
          label="Stations with a forecast"
          value={`${network.stationsForecast} of ${network.stationsTotal}`}
          note="The rest are listed below with the reason"
        />
      </div>
    </Card>
  )
}
