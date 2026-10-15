import { Link } from 'react-router-dom'
import { categoryOf } from '@/lib/aqi'
import { ADVICE } from '@/lib/advice'

interface AdvicePanelProps {
  /** City-average AQI now; picks the advice. Null when no station has a recent reading. */
  aqiNow: number | null
}

/** Dark "What to do now" panel. Phones get the one-paragraph version. */
export function AdvicePanel({ aqiNow }: AdvicePanelProps) {
  const advice = aqiNow === null ? null : ADVICE[categoryOf(aqiNow).key]

  return (
    <aside
      aria-label="What to do now"
      className="flex min-w-0 flex-[1_1_340px] flex-col gap-3 rounded-2xl bg-inverse p-[22px] text-inverse-text md:gap-[18px] md:p-8"
    >
      <p className="hidden text-13 uppercase tracking-caps text-inverse-muted md:block">What to do now</p>
      {advice ? (
        <>
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
        </>
      ) : (
        <>
          <h2 className="font-serif text-28 leading-[1.1] md:text-34">No current reading.</h2>
          <p className="text-inverse-soft">
            Until the stations report again there is no current AQI to base advice on. For official guidance see CPCB
            and SAFAR / IITM.
          </p>
        </>
      )}

      <p className="mt-auto hidden border-t border-inverse-line pt-4 text-13 text-inverse-muted md:block">
        The GRAP stage indicated by today's readings is on the{' '}
        <Link to="/operations" className="text-inverse-text underline underline-offset-2">
          Operations page
        </Link>
        , labelled as indicative.
      </p>
    </aside>
  )
}
