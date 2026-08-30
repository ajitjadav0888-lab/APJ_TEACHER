# APJ Teacher import

The original `APJ_TEACHER` repository is preserved under `apj_build/`. The
existing Android client, web asset, SQLite databases, FastAPI backend, security
notes, and release notes were imported without a rewrite.

## Backend

Run the API locally from the project root:

```bash
cd apj_build/backend
python -m uvicorn app:app --reload
```

The Replit API service runs the same application with the workflow-provided
port. Production uses the same Uvicorn entrypoint and performs a Python
compile check during the build step.

Set `APJ_ENV=production` and provide `APJ_AUTH_SECRET` (or the existing
`SESSION_SECRET`) with at least 32 characters before publishing. `APJ_DATABASE_URL`
can be used to select another SQLAlchemy-compatible database; otherwise the
imported SQLite database is used.