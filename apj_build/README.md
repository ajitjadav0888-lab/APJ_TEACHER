# APJ V1.0 — Session Security Hardened RC

This build adds database-backed session security, refresh-token rotation, logout revocation, production secret enforcement, and failed-login rate limiting on top of the Authorization Hardened RC.

Run locally:

```bash
cd backend
python -m uvicorn app:app --reload
```

For production set `APJ_ENV=production` and a random `APJ_AUTH_SECRET` of at least 32 characters.
