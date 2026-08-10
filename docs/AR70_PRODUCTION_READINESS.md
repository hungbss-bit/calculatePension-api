# AR-70 — Production Readiness V1.0

## Locked scope

V1.0 supports normal retirement estimation only, including pension and retirement one-time allowance. Hazardous/special work, underground coal, reduced-capacity and other special retirement policies remain out of scope.

Post-retirement annual pension increases and the separate social-insurance lump-sum benefit are out of scope.

## Security controls

- API key required in production through `REQUIRE_API_KEY=true`.
- No secrets in source control.
- Request body limit through `MAX_REQUEST_BODY_BYTES`.
- Sanitized HTTP/business/unhandled error responses.
- Security response headers.
- Stateless calculation design; no application database is required by V1.0.
- `calculation_id` is the per-calculation identifier.
- `temporary_id` is only a 12-digit display/reference code for users who do not provide a real BHXH number.
- Real citizen records must not be committed to GitHub.

## CI release gate

Every push and pull request runs the full pytest suite. Any failure blocks certification.

Golden profiles G01–G10 are mandatory regression fixtures. Expected values must never be changed merely to make a failing implementation pass.

## Before production

Replace the placeholder privacy contact and security contact, configure production secrets, review platform logging/retention, enable HTTPS, and perform an external security review.
