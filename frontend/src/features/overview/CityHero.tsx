import { AqiScaleBar } from '@/components/aqi/AqiScaleBar'
import { CategoryPill } from '@/components/aqi/CategoryPill'
import { Card } from '@/components/ui/Card'
import { Eyebrow } from '@/components/ui/Eyebrow'
import type { Overview } from '@/api/schemas'
import { categoryOf, formatAqi } from '@/lib/aqi'
import { formatClock, formatDay, formatPercent, formatSigned } from '@/lib/format'

interface CityHeroProps {
  overview: Overview
}

function Stat({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className={className}>
      <p className="text-12 text-ink-muted md:text-13">{label}</p>
      <p className="mt-0.5 font-mono text-22 md:text-24">{value}</p>
    </div>
  )
}

/** The headline: tomorrow's city-average AQI, its range and where it sits on the CPCB scale. */
export function CityHero({ overview }: CityHeroProps) {
  const { network, validFor, issuedAt } = overview
  const category = categoryOf(network.forecast24h)
  const range = `${formatAqi(network.lo)}–${formatAqi(network.hi)}`
  const scaleLabel = `Tomorrow's forecast of ${formatAqi(network.forecast24h)} is ${category.label}, likely between ${formatAqi(
    network.lo,
  )} and ${formatAqi(network.hi)}, on the CPCB scale of 0 to 500.`

  return (
    <Card
      as="section"
      aria-label="City forecast"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-3.5 p-[22px] md:gap-5 md:px-9 md:py-8"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <Eyebrow className="text-12 md:text-13">
          Tomorrow<span className="hidden md:inline"> · {formatDay(validFor)}</span> · city average
        </Eyebrow>
        <p className="hidden text-13 text-ink-muted md:block">24h ahead · issued {formatClock(issuedAt)} IST</p>
      </div>

      <div className="flex items-end gap-3.5 md:flex-wrap md:gap-x-7 md:gap-y-3">
        <h1 className="font-serif text-96 leading-[0.85] tracking-[-0.02em] md:text-136">
          <span className="sr-only">Forecast AQI </span>
          {formatAqi(network.forecast24h)}
        </h1>
        <div className="flex flex-col gap-2 pb-1.5 md:pb-2">
          <CategoryPill aqi={network.forecast24h} size="md" className="self-start" />
          <p className="hidden text-ink-2 md:block">
            Likely between <span className="font-mono">{formatAqi(network.lo)}</span> and{' '}
            <span className="font-mono">{formatAqi(network.hi)}</span>{' '}
            <span className="text-ink-muted">(80% range)</span>
          </p>
        </div>
      </div>

      <p className="text-ink-2 md:hidden">
        Likely <span className="font-mono">{range}</span> · {formatPercent(network.pSevere)} chance of Severe
      </p>

      <AqiScaleBar
        className="md:hidden"
        thickness={10}
        showAxis={false}
        forecast={network.forecast24h}
        label={scaleLabel}
      />
      <AqiScaleBar
        className="hidden md:flex"
        now={network.now}
        forecast={network.forecast24h}
        range={{ lo: network.lo, hi: network.hi }}
        label={scaleLabel}
      />

      <div className="grid grid-cols-2 gap-3 border-t border-line-soft pt-3 md:grid-cols-3 md:gap-4 md:border-line md:pt-5">
        <Stat label="Right now" value={formatAqi(network.now)} />
        <Stat label="Change by tomorrow" value={formatSigned(network.forecast24h - network.now)} />
        <Stat
          className="hidden md:block"
          label="Chance of Severe (401+)"
          value={formatPercent(network.pSevere)}
        />
      </div>
    </Card>
  )
}
