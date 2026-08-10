# AR-65 — Golden Test & Release Candidate Review

## Scope
V1.0 only: normal retirement, no hazardous/special work, no reduced-capacity retirement, no post-retirement annual adjustment, no BHXH lump-sum withdrawal.

## Automated regression
- pytest: **24 passed**
- API smoke test against local Uvicorn: **PASS**
- OpenAPI operation IDs: **PASS**
- Real SoBHXH repeated calculation: **PASS**
- Missing/masked SoBHXH temporary identity: **PASS**
- PRE-1995 duration with missing salary: **PASS**
- PRE-1995 duration with 262 VND: **PASS**
- Special/reduced-capacity scope rejection: **PASS**
- Calculation trace consistency: **PASS**
- Temporary ID Vietnam timezone: **PASS**

## Important V1.0 invariants
1. PRE-1995 valid duration is never discarded merely because salary/basis is missing.
2. PRE-1995 salary values such as 262 VND are retained for audit but do not automatically become a salary basis in V1.0.
3. A real SoBHXH can be used repeatedly; each calculation receives a different calculation_id.
4. Missing/masked SoBHXH receives a 12-digit YYYYMMDDHHMM temporary_id in Asia/Ho_Chi_Minh time.
5. temporary_id is not a globally unique person identifier; calculation_id is unique per calculation.
6. V1.0 rejects out-of-scope retirement cases instead of guessing.

## Release status
**Release Candidate — not yet Production-certified.**

The remaining certification item is legal/operational verification of the detailed average-salary rules for every mixed salary regime, especially:
- state salary coefficient + allowances;
- state + employer salary;
- compulsory + voluntary;
- transitional/pre-1995 records;
- the exact 2026 adjustment datasets used in production.

The API must not be promoted to Production merely because automated tests pass. Golden expected values must be independently established from the approved BHXH policy/reference data before final release.
