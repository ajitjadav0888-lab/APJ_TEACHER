# APJ V1.0 Regression Fix Retest

## Findings remediated
- Teacher assignment creation now enforces server-side school scope.
- Fee creation now enforces server-side school scope and rejects paid amounts above invoice amount.
- Teacher homework creation now verifies class and subject belong to the requested school and enforces assigned class/subject scope.
- Exam creation is restricted to SUPER_ADMIN/ADMIN; teachers continue to operate within assignment-scoped academic workflows.

## Retest
- Python compilation: PASS
- Cross-school scope guards added to the identified regression findings: PASS (code-level verification)
- Teacher class/subject authorization guard for homework: PASS (code-level verification)
- Fee amount validation: PASS (code-level verification)

## Remaining release gates
- End-to-end full regression execution remains required.
- Performance/concurrency testing remains required.
- Final smoke test remains required.
