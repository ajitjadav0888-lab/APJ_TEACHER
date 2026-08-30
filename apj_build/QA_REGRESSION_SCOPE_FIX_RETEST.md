# APJ V1.0 Regression Scope Fix Retest

## Build under test
APJ V1.0 Regression Scope Fix RC

## Fixes verified
- Timetable creation now calls `require_school_access(user, data.school_id)` before resource processing.
- Fee creation now calls `require_school_access(user, data.school_id)` before student lookup.
- Mark creation now validates that `subject_id` resolves to a subject in the requested school before teacher-scope enforcement.

## Checks executed
- Python compilation of backend modules: PASS
- Static guard verification for timetable school scope: PASS
- Static guard verification for fee school scope: PASS
- Static same-school subject validation in marks flow: PASS

## Release note
This retest closes the three specific findings above. It is not a substitute for the remaining full end-to-end regression, performance test, and final smoke test.
