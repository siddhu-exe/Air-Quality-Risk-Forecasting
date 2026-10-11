import { useState } from 'react'
import type { AlertRule as AlertRuleData, Backtest } from '@/api/schemas'
import { Card } from '@/components/ui/Card'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { formatCount, formatPercent, formatRate } from '@/lib/format'

type RuleId = AlertRuleData['id']

const RULE_NAME: Record<RuleId, string> = { cpcb: 'CPCB line', costAware: 'Cost-aware' }

function describe(rule: AlertRuleData): string {
  return rule.id === 'cpcb'
    ? `Alert when the 24h forecast reaches ${rule.threshold}, the official Severe line. Fewer false alarms, but the forecast is pulled toward the average, so many Severe hours are missed.`
    : `Alert at ${rule.threshold}, the point that minimised cost on validation when a missed Severe hour counts 5× a false alarm. Catches almost everything by alerting almost always.`
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-13 text-ink-muted">{label}</dt>
      <dd className="font-mono text-30">{value}</dd>
    </div>
  )
}

/** Backtest of the two alert thresholds on the held-out winter, switchable. */
export function AlertRule({ backtest }: { backtest: Backtest }) {
  const [selected, setSelected] = useState<RuleId>('cpcb')
  const rules = backtest.alertRules
  const rule = rules.find((r) => r.id === selected) ?? rules[0]
  if (!rule) return null

  return (
    <Card as="section" aria-labelledby="rule-title" className="flex min-w-0 flex-[999_1_560px] flex-col gap-[18px] px-5 py-6 md:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="rule-title" className="text-17 font-semibold">
          Alert rule
        </h2>
        <SegmentedControl
          label="Choose alert threshold"
          value={rule.id}
          onChange={setSelected}
          options={rules.map((r) => ({ value: r.id, label: `${RULE_NAME[r.id]} · ${r.threshold}` }))}
        />
      </div>
      <p className="text-ink-2">{describe(rule)}</p>
      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Severe hours caught" value={formatRate(rule.recall)} />
        <Metric label="Alerts that were right" value={formatRate(rule.precision)} />
        <Metric label="False alarm rate" value={formatRate(rule.falsePositiveRate)} />
        <Metric label="Missed hours" value={formatCount(rule.missedHours)} />
      </dl>
      <p className="border-t border-line-soft pt-3.5 text-13 text-ink-muted">
        Backtest, Nov–Dec 2025, 24h horizon. The cost-aware threshold was chosen on Sep–Oct (only{' '}
        {formatPercent(backtest.severeShare.validation)} Severe hours), so in winter (
        {formatPercent(backtest.severeShare.winter)} Severe) it alerts almost all the time and does no better than
        copy-last.
      </p>
    </Card>
  )
}
