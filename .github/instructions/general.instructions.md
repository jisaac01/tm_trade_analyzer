# General Development Instructions

## Project Focus
- This is a standalone Python project for Monte Carlo trade sizing simulation and trade-performance analysis.
- Keep implementation choices appropriate for a small, single-repo codebase.

## Environment
- Target Python 3.11+.
- Use the active local environment for running scripts/tests.

## Coding Guidelines
- Prefer small, pure functions where possible.
- Keep I/O separated from simulation and analysis logic.
- Preserve deterministic behavior in tests by seeding RNG where needed.

## Data & Paths
- Use project-relative paths for local data files and generated reports.
- Avoid assumptions about external services, databases, or infrastructure.

## Verification
- Run focused tests first (for changed functions), then broader tests if needed.
- Keep test coverage close to numerical logic, argument parsing, and edge cases.

## Documentation
- Keep `README.md` aligned with CLI flags, expected inputs, and outputs.

