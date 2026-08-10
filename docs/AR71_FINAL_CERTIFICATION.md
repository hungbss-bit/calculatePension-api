# AR-71 — Final V1.0 Certification Gate

## Scope

This gate certifies the V1.0 software package only. It does not certify legal benefit entitlement for any individual citizen.

## Mandatory gates

1. Policy Matrix V1.0 present.
2. Golden profiles G01–G10 pass.
3. Regression and API contract tests pass.
4. No citizen records are committed to the repository.
5. No credentials/private keys are committed.
6. Production deployment must set `REQUIRE_API_KEY=true` and provide `API_KEY` through the platform secret store.
7. HTTPS must be enabled at the deployment edge.
8. Docker build must be executed in the release environment before production deployment.

## Explicit V1.0 exclusions

- Hazardous/dangerous occupations and special early-retirement cases.
- Reduced-capacity retirement cases.
- Special military retirement regimes.
- Social-insurance lump-sum benefit (`BHXH một lần`).
- Post-retirement annual pension adjustments.

## Identity

- Real `so_bhxh` is the business identity.
- A real `so_bhxh` may be used for multiple calculations.
- Each calculation has its own `calculation_id`.
- Missing/masked `so_bhxh` receives a Vietnam-time `YYYYMMDDHHMM` temporary identifier.
- `temporary_id` is not a unique primary key.

## Release status

The source package is a Release Candidate until the deployment environment has completed the Docker build and final smoke test. No claim of production certification is made solely from local test success.
