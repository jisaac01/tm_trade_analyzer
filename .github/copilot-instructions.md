## 🚨 CRITICAL RULES (DO NOT IGNORE) 🚨

**Note:** The original file `monte_carlo_trade_sizing.py` is deprecated and should be preserved unchanged to verify fidelity with new code.

1.  **Mandatory TDD:** You MUST write a failing test *before* writing any implementation code.
    -   **Run Tests Correctly:** Use the full path: `tm_trade_analyzer_venv/bin/pytest`. Do NOT use `source ...`.
2.  **Update the 'Lessons & Mistakes to Avoid' section below:**
    -   If the user corrects your logic or behavior, you MUST update the 'Lessons & Mistakes to Avoid' section below with the lesson learned.
    -   Review this section before starting complex tasks.
3.  **Follow `TODO.md`:**
    -   `TODO.md` is the single source of truth for the current project plan.
    -   Update it as tasks are completed or requirements change.
    -   When implementing from the TODO, **do not go past the current Phase** (or the current item, if it's complex or requires a lot of code). Stop and wait for review/confirmation before proceeding to the next chunk.
    -   **Question Assumptions:** Before implementing each step, question assumptions, validate the approach, and ensure it is bulletproofed (e.g., consider alternatives, check for edge cases, and confirm alignment with project goals).
4.  **No "Plan" Confirmation:**
    -   If requirements are clear, just execute. Do not ask "Shall I proceed?" unless the plan is high-risk.

## Scope
- This repository is focused on Monte Carlo trade sizing and related trade analysis in Python.
- Keep solutions lightweight and local to this project.

## Working Style
- Implement directly when requirements are clear.
- Keep changes minimal and focused on the user request.
- Prefer readability over cleverness.

## Python Standards
- Use clear function boundaries and descriptive names.
- Keep dependencies limited to standard library plus explicitly used public packages (for example, `numpy`, `pandas`).
- Add or update tests when behavior changes.

## Data & Security
- Never hardcode credentials, API keys, tokens, or private file paths.
- Use repo-relative paths for project inputs/outputs.
- Do not reference systems or services outside this repository unless the user explicitly asks.

## Validation
- Run the relevant test file(s) after changes when available.
- If no tests exist for a changed behavior, add a focused test in this repo.
- Do not attempt to run the Flask app directly - the user runs it separately. Use integration tests to verify functionality.

## General Development Instructions

### Project Focus
- This is a standalone Python project for Monte Carlo trade sizing simulation and trade-performance analysis.
- Keep implementation choices appropriate for a small, single-repo codebase.

### Environment
- Target Python 3.11+.
- Use the active local environment for running scripts/tests.

### Coding Guidelines
- Prefer small, pure functions where possible.
- Keep I/O separated from simulation and analysis logic.
- Preserve deterministic behavior in tests by seeding RNG where needed.
- **DRY Principle:** Don't Repeat Yourself - extract duplicated logic into reusable functions or shared templates. Maintain single sources of truth for common code patterns.

### Data & Paths
- Use project-relative paths for local data files and generated reports.
- Avoid assumptions about external services, databases, or infrastructure.

### Verification
- Run focused tests first (for changed functions), then broader tests if needed.
- Keep test coverage close to numerical logic, argument parsing, and edge cases.

### Documentation
- Keep `README.md` aligned with CLI flags, expected inputs, and outputs.
- Add detailed tooltips to all user-facing fields, labels, and outputs in web interfaces. Explain how each field is used in the simulator, what simulation modes are, and how outputs are calculated. Include this for any future UI elements.

## Lessons & Mistakes to Avoid

The goal of this section is to prevent recurring mistakes. **If you are corrected by the user, you MUST add the correction here.**

### 🚨 Critical (Do Not Violate)
-   **Mandatory TDD:** Write the failing test first for any behavior change.
-   **Always Run Tests After Changes:** Execute the full test suite (using `tm_trade_analyzer_venv/bin/python -m pytest`) after any code modifications to detect regressions early and ensure code quality.
-   **No Mocks for Core Math:** Do not mock internal simulation/analysis logic; only mock external I/O when needed.
-   **Deterministic Tests:** Seed randomness in tests when asserting numeric behavior.
-   **Project-local Execution:** Use the project environment tools (for example, `tm_trade_analyzer_venv/bin/pytest`) instead of relying on global interpreters.
-   **No Hidden Defaults:** Prefer explicit inputs/config over silent fallbacks when behavior materially changes.
-   **No Backward-Compatibility Additions Unless Requested:** Do not add aliases, fallback paths, fallthrough handling, or compatibility shims unless the user explicitly asks for them.
-   **Keep Scope Tight:** Implement only the requested behavior; avoid adding speculative knobs.
-   **Security Hygiene:** Never hardcode secrets, API keys, or private absolute file paths.

### Strategy Analytics
-   **Spread Risk/Reward Semantics:** For options spread analytics, do NOT label realized close-to-close P/L extremes as theoretical max risk/reward. Keep both metrics separate and explicit:
    - Theoretical max risk/reward must be derived from opening structure (`width`, `credit/debit`).
    - Realized max win/loss must be derived from historical close outcomes.
    - If Monte Carlo is configured to be conservative, cap simulated risk with theoretical max loss while capping reward with realized max win.
-   **Conservative metric selection:** When users request robust summaries, use the exact statistic requested (e.g., median vs p95) and label it explicitly in output to avoid confusion with means or raw maxima.
-   **Printed risk metric vs cap metric:** Distinguish between the printed per-trade risk statistic and the conservative cap statistic. A request to change "Avg Risk per spread" to median does NOT imply changing conservative theoretical cap from p95.

### CLI & UX Scope
-   **Avoid over-engineering CLI knobs:** Implement only what was requested. For trade sizing UX, prefer simple preset distributions over exposing multiple tuning switches unless the user explicitly asks for configurability.

