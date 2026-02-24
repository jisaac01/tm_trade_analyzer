# Lessons & Mistakes to Avoid

The goal of this file is to prevent recurring mistakes. **If you are corrected by the user, you MUST add the correction here.**

## 🚨 Critical (Do Not Violate)
-   **Mandatory TDD:** Write the failing test first for any behavior change.
-   **Test Organization:** Create separate test files for each module in a dedicated `tests/` directory. Do not append tests for new modules to existing test files.
-   **Data File Organization:** Do not place data files (e.g., CSV test files) in inappropriately named folders like 'scripts'. Use descriptive names like 'test_data' or 'data'.
-   **No Mocks for Core Math:** Do not mock internal simulation/analysis logic; only mock external I/O when needed.
-   **Deterministic Tests:** Seed randomness in tests when asserting numeric behavior.
-   **Project-local Execution:** Use the project environment tools (for example, `tm_trade_analyzer_venv/bin/pytest`) instead of relying on global interpreters.
-   **No Hidden Defaults:** Prefer explicit inputs/config over silent fallbacks when behavior materially changes.
-   **Keep Scope Tight:** Implement only the requested behavior; avoid adding speculative knobs.
-   **Security Hygiene:** Never hardcode secrets, API keys, or private absolute file paths.

## Strategy Analytics
-   **Spread Risk/Reward Semantics:** For options spread analytics, do NOT label realized close-to-close P/L extremes as theoretical max risk/reward. Keep both metrics separate and explicit:
    - Theoretical max risk/reward must be derived from opening structure (`width`, `credit/debit`).
    - Realized max win/loss must be derived from historical close outcomes.
    - If Monte Carlo is configured to be conservative, cap simulated risk with theoretical max loss while capping reward with realized max win.
-   **Conservative metric selection:** When users request robust summaries, use the exact statistic requested (e.g., median vs p95) and label it explicitly in output to avoid confusion with means or raw maxima.
-   **Printed risk metric vs cap metric:** Distinguish between the printed per-trade risk statistic and the conservative cap statistic. A request to change "Avg Risk per spread" to median does NOT imply changing conservative theoretical cap from p95.

## CLI & UX Scope
-   **Avoid over-engineering CLI knobs:** Implement only what was requested. For trade sizing UX, prefer simple preset distributions over exposing multiple tuning switches unless the user explicitly asks for configurability.

