# APJ Teacher API

APJ Teacher is a Gujarati educational platform with an Android client and a FastAPI backend for school administration, academics, authentication, fees, and library operations.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the imported FastAPI backend through the API service
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- Required production env: `APJ_AUTH_SECRET` or `SESSION_SECRET` — a random value of at least 32 characters
- Optional env: `APJ_DATABASE_URL` — SQLAlchemy database URL; defaults to the imported SQLite database
- Optional env: `APJ_CORS_ORIGINS` — comma-separated allowed browser origins

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: FastAPI + Uvicorn
- DB: SQLite by default, SQLAlchemy-compatible through `APJ_DATABASE_URL`
- Validation: Pydantic
- Auth: existing database-backed bearer sessions with refresh-token rotation
- Mobile source: imported Android wrapper in `apj_build/android`

## Where things live

- `apj_build/backend/app.py` — FastAPI application, SQLAlchemy models, and domain routes
- `apj_build/backend/auth.py` and `auth_api.py` — credential, session, refresh, logout, and role access controls
- `apj_build/backend/migrations.py` — SQLite schema migration markers
- `apj_build/android` — imported Android project
- `apj_build/frontend` — imported web asset used by the Android wrapper
- `lib/api-spec/openapi.yaml` — workspace scaffold contract; the imported FastAPI routes remain the backend source of truth

## Architecture decisions

- The imported FastAPI backend is served directly rather than rewritten into the workspace's TypeScript scaffold.
- The API service owns the `/` route so existing backend paths such as `/health` and `/api/v1/*` remain unchanged.
- `APJ_AUTH_SECRET` is preferred, with the existing Replit `SESSION_SECRET` as a runtime fallback; production still requires a 32-character secret.
- SQLite remains the default for compatibility with the imported app; deployments can provide another SQLAlchemy URL without changing route code.

## Product

- School, user, class, subject, and student administration
- Session-based login, refresh-token rotation, logout revocation, and role-based access
- Academic years, attendance, homework, exams, marks, results, and report cards
- Teacher assignments, timetables, fee invoices, and library issue/return workflows

## User preferences

- Preserve the imported Android and FastAPI application code unless a deployment or compatibility fix requires a change.

## Gotchas

- Set `APJ_ENV=production` and a random `APJ_AUTH_SECRET` of at least 32 characters for production.
- The imported backend expects to run from `apj_build/backend` because its internal imports are module-local.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
