# AR-74 — Correction: State salary average and one-time retirement allowance

## Root causes

1. For Mẫu 07/SBH records using `unit=coefficient` with `compulsory_state`, the previous engine used the historical monthly base salary for periods from 2016 onward and then applied the annual adjustment coefficient again. This produced a double/incorrect conversion.
2. The one-time retirement allowance was calculated by converting excess months directly to a fraction of a year. The V1.0 rule is instead: 1–6 excess months = 0.5 year; 7–11 excess months = 1 year, then multiply by the applicable months-of-average-salary factor.

## Corrected rules

### State salary by coefficient

`coefficient × base_salary_at_pension_month`

For the B_HUONG2 official profile, the last 60 months are 08/2021–07/2026:

- 2 months × 4.32 × 2,530,000
- 36 months × 4.65 × 2,530,000
- 22 months × 4.98 × 2,530,000

Total = 722,568,000; average = 12,042,800.

### One-time retirement allowance

Excess duration is converted to years:
- 0 months = 0 year
- 1–6 months = 0.5 year
- 7–11 months = 1 year

Then:
- before/at retirement-age eligibility: 0.5 month of average salary per excess year;
- after retirement-age eligibility: 2 months of average salary per excess year.

For B_HUONG2: 467 total months − 360 months = 107 excess months = 9 years;
9 × 0.5 × 12,042,800 = 54,192,600.

## Certification

The regression suite passes 31/31 tests after this correction.
