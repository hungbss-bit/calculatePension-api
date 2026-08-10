# AR-66 — Policy/Engine Review

## Scope
AI Agent Hưu trí V1.0 — nghỉ hưu bình thường only.

## Finding
The previous V1.0.2 RC implementation used a single `remainder_rate` of 1% for 01–06 months and 2% for 07–11 months for all rate groups. That was incorrect for the male 15-to-under-20-year group, whose annual increment is 1%.

## Correction
`calculate_rate()` now converts remaining months to years first:

- 0 months = 0 year
- 01–06 months = 0.5 year
- 07–11 months = 1 year

Then applies the annual increment of the applicable group:

- Female: 2%/year
- Male 15–<20 years: 1%/year
- Male >=20 years: 2%/year

## Regression tests added
- Female 15 years 6 months -> 46%
- Male 15 years 6 months -> 40.5%
- Male 15 years 7 months -> 41%

## Test result
25 passed.

## Important certification status
This correction improves the rate engine, but the package remains a Release Candidate. Production certification still requires independently approved Golden Numerical Test cases for average salary and mixed regimes (State coefficient/allowances, employer salary, compulsory + voluntary, and transitional/pre-1995 records).
