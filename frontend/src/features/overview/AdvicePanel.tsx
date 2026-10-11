import { Link } from 'react-router-dom'
import type { GrapStage } from '@/api/schemas'
import { categoryOf } from '@/lib/aqi'
import { ADVICE } from '@/lib/advice'

interface AdvicePanelProps {
  /** Tomorrow's city-average AQI; picks the advice. */
  forecast24h: number
  grapStageInForce: GrapStage | null
}

/** Dark "What to do tomorrow" panel. Phones get the one-paragraph version. */
export function AdvicePanel({ forecast24h, grapStageInForce }: AdvicePanelProps) {
  const advice = ADVICE[categoryOf(forecast24h).key]

  return (
    <aside
      aria-label="What to do tomorrow"
      className="flex min-w-0 flex-[1_1_340px] flex-col gap-3 rounded-2xl bg-inverse p-[22px] text-inverse-text md:gap-[18px] md:p-8"
    >
      <p className="hidden text-13 uppercase tracking-caps text-inverse-muted md:block">What to do tomorrow</p>
      <h2 className="font-serif text-28 leading-[1.1] md:text-34">{advice.headline}</h2>

      <p className="text-inverse-soft md:hidden">{advice.summary}</p>
      <ol className="hidden flex-col gap-3.5 md:flex">
        {advice.actions.map((action, index) => (
          <li key={action} className="flex gap-3">
            <span aria-hidden="true" className="font-mono text-inverse-accent">
              {String(index + 1).padStart(2, '0')}
            </span>
            <span>{action}</span>
          </li>
        ))}
      </ol>

      <p className="mt-auto hidden border-t border-inverse-line pt-4 text-13 text-inverse-muted md:block">
        {grapStageInForce
          ? `GRAP Stage ${grapStageInForce} restrictions in force. `
          : 'No GRAP restrictions in force. '}
        <Link to="/operations" className="text-inverse-text underline underline-offset-2">
          See stages
        </Link>
      </p>
    </aside>
  )
}
