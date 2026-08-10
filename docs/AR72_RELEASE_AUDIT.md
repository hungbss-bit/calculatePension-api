# AR-72 — Final Release Audit

## Purpose
Final static/runtime audit of the V1.0 Release Candidate before publication to GitHub.

## Checks
- [x] Unit/regression/golden/API tests pass locally.
- [x] Production authentication is secure-by-default (`REQUIRE_API_KEY=true` unless explicitly overridden for tests/local use).
- [x] Secret/data source-hygiene workflow is present.
- [x] Dependency review workflow is present for pull requests.
- [x] Repository excludes local secrets and citizen-record file formats.
- [x] `__pycache__` and `.pytest_cache` are excluded from release package.
- [x] Temporary ID is not treated as a unique primary key.
- [x] `calculation_id` remains unique per calculation.
- [x] V1.0 OUT_OF_SCOPE rules remain unchanged.

## Not certified by local audit
- [ ] Real Docker build in a Docker-capable environment.
- [ ] Real Render deployment smoke test.
- [ ] Production HTTPS certificate verification.
- [ ] Live GPT Action/API-key integration test.

These four items require an actual deployment environment and are intentionally not claimed as PASS here.
