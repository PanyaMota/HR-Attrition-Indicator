# Business Case: Employee Attrition Indicator
**Prepared by:** [Your Name] · Business Analyst
**Audience:** CHRO / VP People · **Status:** Draft for review

---

## 1. The Problem

[Company]'s retail workforce is our largest controllable cost and our most direct
driver of customer experience. Right now, attrition is managed reactively — we
find out an employee is leaving when they hand in notice, not before. By then,
the cost is already locked in.

This project proposes an **Attrition Indicator**: a predictive system that flags
at-risk employees and segments them by *who actually matters to retain*, so
managers and HR can act weeks before an exit, not days after.

## 2. What Attrition Actually Costs Us

Industry research puts the cost of replacing an employee at **50–200% of their
annual salary**, driven by recruiting, onboarding, lost productivity during
ramp-up, and knowledge/relationship loss (particularly acute for store managers
and tenured frontline staff who carry customer relationships and institutional
knowledge).

We estimate replacement cost per role using:

```
EstimatedReplacementCost = AnnualSalary × ReplacementCostFactor
```

| Job Level | Replacement Cost Factor | Rationale |
|---|---|---|
| Frontline | 0.5x | Fast to hire/train, but high volume drives total cost |
| Team Lead | 0.75x | Moderate ramp time, some institutional knowledge loss |
| Store Manager | 1.5x | Long ramp time, P&L ownership, team stability risk |
| Regional / Corporate | 2.0x | High recruiting cost, longest time-to-productivity |

At our current headcount and attrition rate, this translates to an estimated
**$[X]M in annual replacement cost** — [this is the number to calculate from
your dataset once it's loaded; see Section 5].

## 3. Not All Attrition Is Equal

Treating all attrition the same is the single biggest blind spot in most
retention efforts. We distinguish:

- **Regretted attrition** — high performers (rating ≥4) leaving voluntarily.
  This is value walking out the door, and it's the segment this project is
  built to predict and prevent.
- **Non-regretted attrition** — lower performers, involuntary exits, or
  restructuring. Some of this is healthy organizational turnover and isn't a
  retention failure.

A flat "attrition rate" KPI hides this distinction entirely. A 15% attrition
rate where most of it is regretted, high-performer loss is a crisis. The same
15% where most of it is low-performer churn is arguably healthy. **This
project's core contribution is making that distinction visible and
actionable**, not just measuring attrition as a single number.

## 4. What Drives Attrition (and What We'll Track)

Rather than treat attrition prediction as a generic statistical exercise, this
model is grounded in known HR drivers:

- **Compensation equity** — position within pay band, time since last raise
- **Career velocity** — time since last promotion, relative to peers
- **Engagement** — survey scores and, more importantly, the *trend* (declining
  engagement is a stronger signal than a single low score)
- **Manager quality** — span of control and team-level attrition clustering;
  a disproportionate share of regretted attrition traces back to a small
  number of managers
- **Workload** — overtime hours and PTO under-utilization (a frequently missed
  burnout signal)
- **Tenure curve** — attrition risk is non-linear, with known spikes around
  the 1-year mark and again at 3–4 years
- **Life-stage proxies** — commute distance, role level, time in current role

## 5. What This Project Delivers

1. A predictive model that scores active employees on attrition risk monthly
2. A regretted/non-regretted segmentation so retention effort targets the
   employees who matter most
3. An executive dashboard quantifying attrition cost, risk concentration
   (by department, store, manager), and trend over time
4. AI-generated, manager-ready explanations of *why* an employee is flagged
   and *what action* might help — turning a risk score into something a store
   manager can actually act on, not just a number

## 6. Why This Matters for Workforce Planning

Attrition prediction isn't just a retention tool — it feeds directly into:
- **Headcount planning**: anticipating gaps before they open
- **Succession planning**: identifying which manager-level departures would
  create the most disruption
- **Budget forecasting**: replacement cost as a planned line item, not a
  surprise

---

*Note: figures marked [X] are placeholders to be replaced with actual numbers
calculated from the project dataset once loaded (see Week 2 SQL analysis).*
