## 🚨 CRITICAL RULES (DO NOT IGNORE) 🚨
1.  **Mandatory TDD:** You MUST write a failing test *before* writing any implementation code.
    -   **Run Tests Correctly:** Use the full path: `tm_trade_analyzer_venv/bin/pytest`. Do NOT use `source ...`.
2.  **Update `.github/instructions/lessons.md`:**
    -   If the user corrects your logic or behavior, you MUST update `tasks/lessons.md` with the lesson learned.
    -   Review this file before starting complex tasks.
3.  **Follow `TODO.md`:**
    -   `TODO.md` is the single source of truth for the current project plan.
    -   Update it as tasks are completed or requirements change.
    -   When implementing from the TODO, **do not go past the current Phase** (or the current item, if it's complex or requires a lot of code). Stop and wait for review/confirmation before proceeding to the next chunk.
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

## Reference
- See `general.instructions.md` for additional project conventions.

