# APJ V1.0 Privilege-Escalation Regression

## Finding fixed
A school ADMIN could previously submit `role=SUPER_ADMIN` to `/users`. The endpoint now rejects that escalation with HTTP 403.

## Regression checks
- ADMIN creating TEACHER in own school: allowed by role policy.
- ADMIN creating SUPER_ADMIN: blocked with 403.
- SUPER_ADMIN creating SUPER_ADMIN: allowed by role policy.
- Non-SUPER_ADMIN cannot choose a different school because `target_school` is derived from the authenticated user's school.
- Python compilation: PASS.

## Status
Privilege-escalation fix: PASS.
Full runtime E2E and load testing remain separate release gates.
