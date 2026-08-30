# APJ development test account

The project now has a clearly marked, temporary development-only teacher account:

- Login user ID: `8`
- Display name: `APJ Temporary Development Teacher`
- Role: `TEACHER`
- Database: local development SQLite database only

No password was created in the repository, displayed in chat, or written to
disk. Set the password interactively from the project root:

```bash
APJ_ENV=development python scripts/dev_teacher.py set-password 8
```

The command asks for the password twice with hidden input. Use at least eight
characters. Then log in through `POST /api/v1/auth/login` with:

```json
{
  "user_id": 8,
  "password": "<the password you entered interactively>"
}
```

The utility refuses to run unless `APJ_ENV=development` is explicit and only
allows the marked test teacher. It does not create an HTTP registration or
password-reset route. It also does not change the Android application or the
existing authentication routes.