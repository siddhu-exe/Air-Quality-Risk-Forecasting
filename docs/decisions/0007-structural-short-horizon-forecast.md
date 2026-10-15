# 0007. Structural 1h/6h forecast from PM2.5 forecasts (proposed, not built)

**Status:** proposed. Nothing in this record is implemented.

**Context.** At 1h the window-update rule beats the retrained model; at 6h the rule is no better than persistence because six unknown hours enter the window (ADR 0006).
The rule assumes the entering hourly AQI values stay at the current value. That assumption is the part a forecast can improve.

**Proposal.** Keep the window identity and replace the flat assumption with forecast values: predict the next `h` hourly AQI values `H(t+1..t+h)` (from the
PM2.5 models' forecasts, which are the dominant sub-index in winter, with other pollutants held at their current sub-index or forecast separately) and plug them into
`AQI(t+h) = AQI(t) + sum (H(t+k) - H(t+k-24)) / 24`. The structure carries the arithmetic exactly and leaves the models only the part that is genuinely uncertain.

**Evaluation rules.**
- Any design choice is selected on validation only.
- It is evaluated on live or replay data collected after 2026-10-15, not on the Nov-Dec 2025 test window, which has already been examined for the baseline.
- Reported against plain persistence and against window-update persistence, with day-block bootstrap CIs.

**Consequences if accepted.** A new product version replaces the 1h rule and possibly the 6h model only if it beats both baselines on the post-2026-10-15 data; the
rule stays as the reference in model health either way.
