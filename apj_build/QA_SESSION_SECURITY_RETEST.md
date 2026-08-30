# APJ V1.0 — Session Security Retest

## Implemented
- Database-backed auth sessions.
- Access tokens now carry a session ID and are rejected after session revocation.
- Refresh tokens are stored only as HMAC hashes.
- Refresh-token rotation invalidates the previously presented refresh token.
- Logout revokes the active session.
- Production mode requires `APJ_AUTH_SECRET` (minimum 32 characters).
- Failed-login rate limiting is enabled for the RC (10 failures / 5 minutes per user ID).
- Added `/api/v1/auth/refresh` and `/api/v1/auth/logout`.

## Executed checks
- Login: PASS (200)
- Authenticated `/me`: PASS (200)
- Refresh token: PASS (200)
- Refresh-token reuse: PASS (401)
- Logout: PASS (200)
- Access after logout: PASS (401)
- Failed login attempts 1-10: PASS (401)
- Failed login attempt 11: PASS (429 rate limited)
- Python compilation: PASS

## Status
Session-security RC checks: PASS.

## Remaining production gates
- Shared/distributed rate limiter (current RC limiter is process-local).
- Full automated regression across all modules.
- Backup/restore verification.
- Database migration framework.
- Production deployment/security review.
