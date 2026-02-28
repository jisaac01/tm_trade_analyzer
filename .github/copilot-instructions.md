## 🚨 CRITICAL RULES (DO NOT IGNORE) 🚨

**Note:** The original file `monte_carlo_trade_sizing.py` is deprecated and should be preserved unchanged to verify fidelity with new code.

1.  **Be Concise:**
2.  **Mandatory TDD:** You MUST write a failing test *before* writing any implementation code.
3.  **🚨 ALWAYS USE DIRECT PYTEST PATH: `tm_trade_analyzer_venv/bin/pytest` 🚨**
    -   **NEVER** use `tm_trade_analyzer_venv/bin/python -m pytest`
    -   **NEVER** use `source ... && pytest`
    -   **ALWAYS** use the full direct path: `tm_trade_analyzer_venv/bin/pytest`
    -   This allows auto-approval of test runs.
4.  **Follow Testing Guidelines:** Read [docs/TESTING_GUIDELINES.md](docs/TESTING_GUIDELINES.md) - Integration tests with real data preferred over mocked tests.
5.  **Update the 'Lessons & Mistakes to Avoid' section below:**
    -   If the user corrects your logic or behavior, you MUST update the 'Lessons & Mistakes to Avoid' section below with the lesson learned.
    -   Review this section before starting complex tasks.
6.  **Follow `TODO.md`:**
    -   `TODO.md` is the single source of truth for the current project plan.
    -   Update it as tasks are completed or requirements change.
    -   When implementing from the TODO, **do not go past the current Phase** (or the current item, if it's complex or requires a lot of code). Stop and wait for review/confirmation before proceeding to the next chunk.
    -   **Question Assumptions:** Before implementing each step, question assumptions, validate the approach, and ensure it is bulletproofed (e.g., consider alternatives, check for edge cases, and confirm alignment with project goals).
7.  **No "Plan" Confirmation:**
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

## Validation & Testing

**IMPORTANT:** Follow the comprehensive [Testing Guidelines](docs/TESTING_GUIDELINES.md) for all test-related work.

### Test Quality Requirements
- **Integration Tests First:** Prefer full end-to-end tests with real CSV files over mocked unit tests
- **Test Actual Values:** Verify specific calculated values (exact P/L, percentages, dates), not just structure/types
- **Use Real Data:** Use CSV files from `tests/test_data/` - synthetic data hides bugs
- **Minimize Mocking:** Only mock external APIs or unavoidable I/O. NEVER mock internal simulation/parsing logic
  - Mock warnings will appear when using `patch()` or `Mock()` - they should be rare
  - If you must mock, use `@suppress_mock_warnings` decorator and add a comment explaining why
- **Deterministic Tests:** Always seed RNG for Monte Carlo tests (`random_seed=42`)
- **Small Simulations:** Use `num_simulations=5-10` in tests for speed (not 1000)

### Quick Test Examples
```python
# ✅ GOOD: Integration test with real data
def test_simulation_with_real_trades():
    trade_stats = parse_trade_csv('tests/test_data/sample_trades.csv')
    result = run_monte_carlo_simulation(trade_stats, initial_balance=10000, 
                                        num_simulations=10, random_seed=42)
    assert 9000 < result['median_final_balance'] < 11000  # Actual value
    assert result['bankruptcy_probability'] < 0.5

# ❌ BAD: Heavy mocking of internal code
@patch('simulator.calculate_balance')  # Don't mock our own code!
def test_app_simulation(mock_calc):
    mock_calc.return_value = {'balance': 11000}
    # This tests nothing useful
```

### Test Execution
- Run focused tests first: `tm_trade_analyzer_venv/bin/pytest tests/test_module.py`
- Run full suite after changes: `tm_trade_analyzer_venv/bin/pytest`
- Always run tests after code modifications to catch regressions

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
- **File Creation:** When creating temporary or analysis files, create them WITHIN the workspace (e.g., in a `scripts/` folder) rather than in system directories like `/tmp/`. 

### Documentation
- Keep `README.md` aligned with CLI flags, expected inputs, and outputs.
- Add detailed tooltips to all user-facing fields, labels, and outputs in web interfaces. Explain how each field is used in the simulator, what simulation modes are, and how outputs are calculated. Include this for any future UI elements.

## Lessons & Mistakes to Avoid

The goal of this section is to prevent recurring mistakes. **If you are corrected by the user, you MUST add the correction here.**

### 🚨 Critical (Do Not Violate)
-   **Mandatory TDD:** Write the failing test first for any behavior change.
-   **🚨 PYTEST PATH: ALWAYS use `tm_trade_analyzer_venv/bin/pytest` (NOT `python -m pytest`) 🚨** - This allows auto-approval of test runs.
-   **Always Run Tests After Changes:** Execute the full test suite after any code modifications to detect regressions early and ensure code quality.
-   **Follow Testing Guidelines:** See [docs/TESTING_GUIDELINES.md](docs/TESTING_GUIDELINES.md) for comprehensive testing standards. Key principles:
    - Integration tests > Unit tests > Mocked tests
    - Real CSV data > Synthetic data
    - Actual values > Structure checks
    - NEVER mock internal simulation/parsing logic (only external APIs/I/O when necessary)
    - Use `@suppress_mock_warnings` decorator with justification comment if mocking is genuinely required
-   **Deterministic Tests:** Seed randomness in tests when asserting numeric behavior.
-   **No Hidden Defaults:** Prefer explicit inputs/config over silent fallbacks when behavior materially changes.
-   **No Silent Error Swallowing / Fail Fast on Invalid Data:** When required data is missing or invalid, raise clear errors immediately instead of falling back to buggy behavior. Never use fallbacks like `if data_exists else broken_fallback()` or `value if value > 0 else 0` - if the data is required, fail loudly with an informative error message. Examples:
    - ❌ WRONG: `pnl_pct = (pnl / risk * 100) if risk > 0 else 0.0` (hides CSV data quality issues)
    - ✅ CORRECT: Validate `risk > 0` upfront and raise ValueError with specific details (date, value, likely cause)
    - This surfaces CSV data quality issues (missing prices, invalid spreads) immediately rather than hiding them with silent fallbacks
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

### Data Parsing & Integrity  
-   **Preserve File Order:** When parsing CSV data, maintain chronological order from the source file. Use `sort=False` in pandas groupby operations to prevent alphabetical sorting.
-   **Verify Alignment:** After any groupby or join operation, verify that related lists (dates, P/L, theoretical risk) remain aligned. Index i in one list must correspond to index i in all related lists.
-   **Data Quality Validation:** Flag trades with missing prices, impossible returns (losses > theoretical max + commissions), or other integrity issues. Don't silently accept corrupt data.
-   **Commission Handling:** Per-spread commissions are `4 legs × $0.495 = $1.98`. Use this for validation buffers, not arbitrary percentages.
-   **Required Data Validation:** If closing P/L data exists but opening data is missing or mismatched, raise a clear error immediately. The simulator cannot function without opening data for theoretical metrics and dates. Never fall back to potentially buggy behavior when data integrity is compromised.

### Position Sizing & Broker Constraints
-   **Position size must respect account balance:** The simulator must ALWAYS cap position sizing such that `max_risk_per_spread * contracts <= current_balance`. This simulates real broker margin requirements - a broker would never allow opening a position whose theoretical max loss exceeds the account balance. Even if a trader always takes losses to the theoretical maximum, the account balance can never go negative.
-   **CRITICAL: Position sizing must use same risk method as loss simulation:**
    - **Position sizing constraint (broker margin):** Use `get_position_sizing_risk_per_spread(trade, risk_calculation_method)` which uses the SAME risk method as loss simulation. This determines HOW MANY contracts can be traded.
    - **Loss simulation amount:** Use `get_max_risk_per_spread(trade, risk_calculation_method)` which respects the selected method. This determines HOW MUCH is lost on a losing trade.
    - **Why they must match:** If position sizing uses conservative_theoretical ($180) but loss simulation uses max_theoretical ($220), you could approve 5 contracts (5*180=$900 ≤ $1000) but then lose 5*220=$1100 > $1000, causing negative balance! Both must use the same risk method.
    - **Default behavior:** If risk_calculation_method is NOT 'max_theoretical' or 'fixed_theoretical_max', position sizing uses conservative_theoretical (p95) for safety.
    - **When user chooses max_theoretical:** Position sizing MUST also use max_theoretical to maintain the constraint that max_risk * contracts ≤ balance.
-   **CRITICAL: Bootstrap mode MUST use per-trade risks for position sizing:**
    - **The Bug:** Bootstrap simulation was sampling P/L from historical trades but using aggregate risk metrics (e.g., p95=$717) for ALL position sizing, while replay used each trade's specific risk ($176 to $1421). This caused massive discrepancies: replay bankrupted but bootstrap showed 0% bankruptcy probability.
    - **The Fix:** When sampling trades in bootstrap mode, sample BOTH P/L AND per-trade theoretical risks together using `sample_trades_moving_blocks()`. Use the sampled risk for position sizing, not aggregate metrics.
    - **Why it matters:** When we sample a trade's P/L, we must use THAT trade's specific theoretical risk for position sizing to match what would happen in reality. Otherwise, position sizing is mismatched with the actual trade outcomes, making bootstrap simulation meaningless.
    - **Implementation:** Use `current_position_sizing_risk = sampled_trade_risks[trade_idx]` (not aggregate `position_sizing_risk`) for affordability checks, dynamic sizing, and all position sizing constraints within the bootstrap simulation loop.
-   **Cap applies universally:** Position size capping must apply to all simulation modes: fixed contract sizing, dynamic risk-based sizing, IID mode, and bootstrap mode.
-   **No forced trades:** Never use `max(1, int(balance / risk))` as this forces 1 contract even when balance < risk per contract. If account cannot afford even 1 contract, stop trading (bankruptcy).
-   **Replay consistency:** When generating summary statistics for trade replay, ensure position sizing constraints (e.g., affordability checks) match the *actual* first trade conditions, not aggregate statistics. If the replay engine validates affordability against the first trade's specific risk, the summary plan must do the same to avoid discrepancies in contract counts.
