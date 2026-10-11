import type { Backtest } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { ProgressBar } from '@/components/ui/ProgressBar'
import { formatRate } from '@/lib/format'
import { leadTimeHorizonLabel, leadTimeNote } from '@/lib/leadTime'

function Row({ label, value, fill, muted }: { label: string; value: number; fill: string; muted?: boolean }) {
  return (
    <>
      <span className={muted ? 'text-ink-muted' : undefined}>{label}</span>
      <ProgressBar value={value} fillClassName={`h-full ${fill}`} size="lg" />
      <span className="text-right font-mono">{formatRate(value)}</span>
    </>
  )
}

/** Share of past Severe episodes each method warned about, and how early. */
export function LeadTimes({ leadTimes }: { leadTimes: Backtest['leadTimes'] }) {
  return (
    <Card as="section" aria-labelledby="lead-title" className="flex min-w-0 flex-[1_1_380px] flex-col gap-[18px] px-7 py-6">
      <h2 id="lead-title" className="text-17 font-semibold">
        Early warning, past winter
      </h2>
      {leadTimes.map((lead) => (
        <div key={lead.horizon} className="flex flex-col gap-2">
          <p className="font-medium">
            {leadTimeHorizonLabel(lead.horizon)} ahead{' '}
            <span className="font-normal text-ink-muted">· {lead.episodes} Severe episodes</span>
          </p>
          <div className="grid grid-cols-[96px_minmax(0,1fr)_48px] items-center gap-2.5 text-13">
            <Row label="Model" value={lead.modelDetectionRate} fill="bg-accent" />
            <Row label="Copy-last" value={lead.persistenceDetectionRate} fill="bg-ink-subtle" muted />
          </div>
          <p className="text-13 text-ink-2">{leadTimeNote(lead)}</p>
        </div>
      ))}
    </Card>
  )
}
