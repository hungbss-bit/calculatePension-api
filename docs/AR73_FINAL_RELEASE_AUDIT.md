# AR-73 — Final Release Audit

## Purpose
Final local audit of the calculatePension API V1.0 release candidate before deployment.

## Completed checks
- [x] Runtime/API/engine version synchronized to `1.0.5-rc`.
- [x] Policy version remains `VN-BHXH-PENSION-V1.0-2026`.
- [x] 27 existing certification/regression/golden/API tests pass.
- [x] Security tests added for headers, request-body limit and API-key enforcement.
- [x] Request-body limit is enforced even when `Content-Length` is absent.
- [x] Internal exception details are not exposed to API clients.
- [x] API authentication remains secure-by-default.
- [x] Source-hygiene workflow and dependency review workflow present.
- [x] No citizen record files are included in the release package.
- [x] Release package excludes Python/cache artifacts.

## Deployment-only checks
The following require a real Docker/Render environment and are not claimed as local PASS:
- Docker image build.
- Live HTTPS endpoint.
- Render health check.
- Live API-key integration.
- GPT Action integration.

## V1.0 scope lock
No expansion is introduced for hazardous/special retirement, underground coal, reduced-capacity retirement, BHXH one-time payment, or post-retirement annual pension adjustments.
