# APJ Credential Security Retest

## Finding
The credential provisioning endpoint allowed an ADMIN to set a password for a user outside the ADMIN's school. This could enable cross-school account takeover.

## Fix
- Enforced target-user school scope in `set_credential`.
- Credential changes revoke all active sessions for the target user.
- Updated auth API to pass the authenticated actor into credential provisioning.

## Static verification
- Python compilation: PASS
- Cross-school credential scope guard: PASS
- Session revocation on credential change: PASS

## Release impact
This is a security hardening fix. Full runtime E2E and performance testing remain required before production GO.
