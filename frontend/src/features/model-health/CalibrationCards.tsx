import type { Backtest, ModelHealth } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { formatPercent } from '@/lib/format'

interface CalibrationCardsProps {
  calibration: ModelHealth['calibration']
  /** Season-level reference numbers; the cards still work without them. */
  backtest: Backtest | undefined
}

const TARGET_COVERAGE = 0.8
/** Briers closer than this are reported as a tie, not a win. */
const BRIER_TIE = 0.005

const brier = (n: number): string => n.toFixed(3)

function brierVerdict(model: number, persistence: number): string {
  if (Math.abs(model - persistence) < BRIER_TIE) return 'a tie'
  return model < persistence ? 'the model ahead' : 'copy-last ahead'
}

function Tile({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col gap-2.5 px-6 py-[22px]">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </Card>
  )
}

/** How honest the probabilities are: range coverage, Brier score, and the season's Severe share. */
export function CalibrationCards({ calibration, backtest }: CalibrationCardsProps) {
  return (
    <section aria-label="Calibration" className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4">
      <Tile title="80% range coverage">
        <p className="font-mono text-32">{formatPercent(calibration.coverage80)}</p>
        <div aria-hidden="true" className="relative h-2 rounded-full bg-line-soft">
          <span
            className="absolute inset-y-0 left-0 rounded-full bg-accent"
            style={{ width: `${Math.min(calibration.coverage80, 1) * 100}%` }}
          />
          <span className="absolute -top-1 h-4 w-0.5 bg-ink" style={{ left: `${TARGET_COVERAGE * 100}%` }} />
        </div>
        <p className="text-13 text-ink-muted">
          Target {formatPercent(TARGET_COVERAGE)}
          {backtest && ` · backtest winter ${formatPercent(backtest.coverage80)}`}
        </p>
      </Tile>

      <Tile title="Severe probability (Brier)">
        <p className="font-mono text-32">
          {brier(calibration.brierModel)}{' '}
          <span className="text-15 text-ink-muted">vs {brier(calibration.brierPersistence)}</span>
        </p>
        <p className="text-13 text-ink-2">
          Lower is better; second number is copy-last.
          {backtest &&
            ` Backtest: ${brier(backtest.brierModel)} vs ${brier(backtest.brierPersistence)}, ${brierVerdict(
              backtest.brierModel,
              backtest.brierPersistence,
            )}.`}
        </p>
      </Tile>

      <Tile title="Severe hours in last 30 days">
        <p className="font-mono text-32">{formatPercent(calibration.severeShare30d)}</p>
        <p className="text-13 text-ink-2">
          {backtest
            ? `Validation season had ${formatPercent(backtest.severeShare.validation)}, last winter ${formatPercent(
                backtest.severeShare.winter,
              )}. Thresholds tuned in one season drift in the other.`
            : 'Thresholds tuned in one season drift in the other.'}
        </p>
      </Tile>
    </section>
  )
}
