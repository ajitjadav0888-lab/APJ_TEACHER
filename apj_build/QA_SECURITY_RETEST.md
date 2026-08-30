# APJ V1.0 Security Remediation Retest

## Verified in this build
- Protected student listing requires authentication and an authorized role.
- Server-side school scope blocks cross-school access with HTTP 403.
- Academic attendance rejects cross-school requests before resource access.
- Result and report-card endpoints require authorized roles and school scope.
- Fee/student listing requires authorized roles and school scope.
- User creation for normal admins is forced to the authenticated admin's school; only SUPER_ADMIN may select another school.
- Production `APJ_AUTH_SECRET` is required by configuration; development fallback is explicitly non-production.
- Python compilation passes.
- Security smoke test passed: same-school access 200, cross-school student access 403, cross-school attendance 403, unauthenticated result access 401.

## Still blocked for full production certification
- Parent-to-child link table and ownership checks are not yet implemented.
- Teacher-to-student/class assignment enforcement is incomplete for endpoints whose payload lacks a class identifier.
- Refresh-token revocation, rate limiting, migrations, full regression suite, backup/restore, and deployment review remain.

Release status: **NOT PRODUCTION READY**.
