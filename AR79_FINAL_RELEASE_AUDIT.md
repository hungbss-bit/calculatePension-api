# AR79 Final Release Audit — Early Retirement Case 1 + Case 2

## Scope

This release preserves the calculation behavior already validated in V1.0/AR77 and the AR78 Render keep-warm workflow. It adds only two controlled early-retirement branches:

1. `reduced_capacity` + `none`: early retirement due to reduced working capacity.
2. `normal` + `decree_154_streamlining`: early retirement under Nghị định 154/2025/NĐ-CP.

Hazardous/special-region, underground-coal and other special policies remain outside the V1.x automation scope.

## Regression results

- Full test suite: **33 passed**.
- B_HUONG1 official regression preserved.
- O_Quy2 mixed State + employer official regression preserved.
- ND154 official ground-truth regression added and passing:
  - 431 months (35 years 11 months)
  - average 19,117,846 VND/month
  - rate 75%
  - early-retirement reduction 0%
  - pension 14,338,385 VND/month
  - retirement one-time allowance 57,353,538 VND
- Case 1 unit regression added:
  - 61% impairment
  - 240 compulsory months
  - 6 months early
  - reduction 1%

## API contract

- Server: `https://calculatepension-api.onrender.com`
- `GET /health` remains public for AR78 keep-warm.
- Calculation endpoints continue to require `X-API-Key`.
- OpenAPI JSON/YAML and `SCHEMA_V1.0_Deploy.json` regenerated from the runtime schema and explicitly include the Render server.

## GPT workflow requirement

When a user requests a pension start date before normal retirement age, GPTs must ask which policy applies before calling the calculation API:

- Case 1 — reduced working capacity.
- Case 2 — Nghị định 154/2025/NĐ-CP streamlining.

The API does not infer the policy from age alone.
