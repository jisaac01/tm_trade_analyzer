# Web App Conversion Plan

## Phase 1: Environment & Setup
- [x] **Step 1.1:** Create `requirements.txt` including `Flask`, `pandas`, `numpy`, `pytest`, and `Werkzeug` (for secure file uploads).
- [x] **Step 1.2:** Set up the Python virtual environment (`tm_trade_analyzer_venv`) and install dependencies.
- [x] **Step 1.3:** Create the basic Flask application structure:
  - `app.py` (main application entry point)
  - `templates/` (for HTML files)
  - `static/` (for CSS/JS files)
  - `uploads/` (temporary directory for uploaded CSVs, added to `.gitignore`)

## Phase 2: Refactoring Core Logic
- [x] **Step 2.1:** Extract the core simulation logic from `monte_carlo_trade_sizing.py` into a new module (e.g., `simulator.py`). It should accept parameters (balance, simulations, commission, etc.) via function arguments rather than CLI args.
- [x] **Step 2.2:** Extract the CSV parsing logic into a new module (`trade_parser.py`) that can accept a file stream or path. Create separate tests in `test_trade_parser.py`.
- [X] **Step 2.3:** Ensure new tests exist for the refactored modules (`test_simulator.py` and `test_trade_parser.py`) with good coverage (simulator: 93%, trade_parser: 100%). Added comprehensive unit tests covering all paths, command line switches, risk/reward generation, position sizing, sampling methods, and edge cases for high confidence in simulation accuracy.
- [x] **Step 2.4:** Update existing tests in `test_monte_carlo_trade_sizing.py` to use the refactored `simulator.py` and `trade_parser.py` modules. Run `pytest` to ensure 100% coverage is maintained.

## Phase 3: Building the Web Interface
- [X] **Step 3.1:** Create a base HTML template (`templates/base.html`) with basic styling (can reuse the CSS from the current HTML report).
- [X] **Step 3.2:** Create the main index page (`templates/index.html`) containing a web form.
- [X] **Step 3.3:** Add form inputs for all configurable options:
  - CSV File Upload (`<input type="file">`)
  - Initial Balance (Number)
  - Number of Simulations (Number)
  - Option Commission (Number)
  - Position Sizing Mode (Dropdown: Percent / Contracts)
  - Dynamic Risk Sizing (Checkbox)
  - Simulation Mode (Dropdown: IID / Bootstrap)
  - Block Size (Number)
- [X] **Step 3.4:** Implement the Flask route (`/`) in `app.py` to render this form.

## Phase 4: Integration & Processing
- [X] **Step 4.1:** Implement secure file upload handling in the `/` POST route. Validate the file extension is `.csv`.
- [X] **Step 4.2:** Connect the form submission to the `simulator.py` logic. Pass the uploaded file and form parameters to the simulator.
- [X] **Step 4.3:** Refactor the HTML report generation. Instead of `build_html_report` returning a hardcoded HTML string, convert it into a Jinja2 template (`templates/results.html`) and pass the simulation results (trade reports, summaries) to it for rendering. **Note:** `build_html_report` function is no longer needed and can be removed.

## Phase 5: Polish & "Quality Product" Features
- [X] **Step 5.1:** Add backend input validation (e.g., ensuring block size > 0, balance > 0) and use Flask `flash` messages to show errors to the user. **Note:** Basic validation implemented; flash messages added for file upload errors.
- [X] **Step 5.2:** Implement basic session management. Store the parsed CSV data (or file path) in the user's session so they can tweak simulation parameters and re-run without having to re-upload the CSV every time.
- [X] **Step 5.3:** Add a loading spinner/overlay on the frontend using simple JavaScript. Monte Carlo simulations can take a few seconds, so visual feedback is critical for a quality product.
- [ ] **Step 5.4:** (Optional but recommended) Move the simulation processing into a background thread or use AJAX/Fetch API to prevent the browser from timing out or appearing frozen during heavy calculations. (Skip for now)

## Phase 6: Historical Trade Replay Feature
- [X] **Step 6.1:** Write tests for `replay_actual_trades()` function that applies position sizing rules to actual historical trade sequence.
- [X] **Step 6.2:** Implement `replay_actual_trades()` function in `simulator.py` that:
  - Takes actual P/L distribution (in order from historical trades)
  - Applies same position sizing rules as Monte Carlo (fixed contracts or dynamic risk %)
  - Tracks balance evolution, max drawdown, and losing streaks
  - Returns detailed metrics including balance history for potential charting
- [X] **Step 6.3:** Extract any shared balance-tracking logic into small helper functions (without adding branching to existing simulator code).
- [X] **Step 6.4:** Add `replay_actual_trades()` to the simulation workflow in `app.py` to run alongside Monte Carlo simulation.
- [X] **Step 6.5:** Update results template to display historical replay results alongside Monte Carlo results with clear labeling.

## Phase 7: Historical Replay Trade Details Table
**Goal:** Add a detailed trade-by-trade table below the historical replay section showing per-trade metrics including dates, P/L, and risk amounts.

- [X] **Step 7.1:** Write tests for `trade_parser.parse_trade_csv` to return per-trade dates (opening date for each expiration group).
- [X] **Step 7.2:** Modify `trade_parser.parse_trade_csv` to extract and return `per_trade_dates` list (opening date for each trade, matched to pnl_distribution order).
- [X] **Step 7.3:** Write tests for `replay.replay_actual_trades` to return per-trade details including: date, contracts, pnl per contract, total pnl, theoretical risk, previous balance, new balance.
- [X] **Step 7.4:** Modify `replay.replay_actual_trades` to return `trade_details` list in addition to summary metrics.
- [X] **Step 7.5:** Write integration tests for app.py replay table generation with multiple scenarios.
- [X] **Step 7.6:** Modify `app.py` to collect per-trade details from replay and pass to template for each scenario.
- [X] **Step 7.7:** Modify `templates/results.html` to add:
  - Dropdown selector for scenario selection
  - Detailed trade table for each scenario (hidden by default, shown via JS)
  - Columns: Previous Balance, Date, P/L $, P/L %, Theoretical Risk $, Theoretical Risk %, New Balance
  - Final row showing final balance only
- [X] **Step 7.8:** Add JavaScript to handle scenario selection and show/hide appropriate tables without page reload.

## Phase 8: Reward Calculation Method (Profit Capping)
**Goal:** Add parallel functionality to Risk Calculation Method that allows testing how early profit-taking affects Monte Carlo simulations.

### Implementation Approach
Profit-taking caps are applied as: `actual_reward = min(generated_reward, profit_cap)`. This means profits are only locked in early if the trade would have exceeded the cap; otherwise, the lower generated value is taken.

### Reward Calculation Methods
- `no_cap` (default): Current behavior, no profit cap
- Cap at X% of Conservative Theoretical Max (p95 from opening structure): 25%, 40%, 50%, 75%
- Cap at X% of Theoretical Max (from opening structure): 25%, 40%, 50%, 75%
- Cap at X% of Average Realized (mean of historical wins): 25%, 40%, 50%, 75%
- Cap at X% of Conservative Realized Max (p95 of historical wins): 25%, 40%, 50%, 75%

Total: 17 methods (1 no_cap + 16 capping variants)

### Steps
- [X] **Step 8.1:** Write tests for `get_reward_cap_per_spread()` function
  - Test all 17 reward calculation methods
  - Test that default ('no_cap') returns None
  - Test with missing reward data (should raise ValueError with clear message)
  - Test that percentages are correctly applied (e.g., 50% of $200 = $100)
- [X] **Step 8.2:** Implement `get_reward_cap_per_spread(trade, reward_calculation_method='no_cap')` in `simulator.py`
  - Return None for 'no_cap' (default)
  - Parse method string to extract percentage and base metric
  - Calculate cap from trade stats dict
  - Raise ValueError if required data missing
  - Follow same error handling pattern as `get_max_risk_per_spread()`
- [X] **Step 8.3:** Write tests for reward capping in `simulate_trades()`
  - Test that generated rewards are capped when reward_calculation_method is set
  - Test that rewards below cap are not affected
  - Test with both IID and bootstrap modes
  - Test that no_cap preserves current behavior
  - Test interaction with contract counts (cap should scale: cap_per_spread * contracts)
- [X] **Step 8.4:** Update `simulate_trades()` to apply reward caps
  - Add `reward_calculation_method='no_cap'` parameter
  - Call `get_reward_cap_per_spread()` to get cap value
  - Apply `min(reward, cap)` logic when generating rewards (if cap is not None)
  - Ensure logic works for both IID mode (generated rewards) and bootstrap mode (historical P/L should not be capped)
- [X] **Step 8.5:** Update `run_monte_carlo_simulation()` to accept and pass through `reward_calculation_method`
  - Add parameter with default 'no_cap'
  - Pass to `simulate_trades()` in all calls
  - Update docstring
- [X] **Step 8.6:** Write integration tests in `test_app.py`
  - Test form submission with reward_calculation_method parameter
  - Test that simulator receives the parameter correctly
- [X] **Step 8.7:** Update `app.py` Flask routes to handle reward_calculation_method
  - Accept from form POST data with default 'no_cap'
  - Pass to `run_monte_carlo_simulation()`
  - Store in session for re-runs
- [X] **Step 8.8:** Update `templates/_simulation_form.html` to add reward calculation dropdown
  - Add form group in Advanced Options section (below risk_calculation_method)
  - Create dropdown with all 17 options, grouped by metric type
  - Add comprehensive tooltip explaining the feature and each option
  - Set default to 'no_cap'
- [X] **Step 8.9:** Run full test suite and verify no regressions
  - Run `tm_trade_analyzer_venv/bin/python -m pytest -v`
  - Manually test in browser with various reward cap settings
  - Verify results make intuitive sense (capping should reduce final balances)


## Phase 9: Separate Outcome Sampling from Magnitude Sampling
**Goal:** Decouple win/loss determination from profit/loss magnitude to enable flexible simulation modes. This allows testing scenarios like "preserve historical win rate patterns but use different profit/loss distributions."

### Current State
- **IID mode**: Outcome determined by win_rate (independent), magnitude from distributions
- **Bootstrap mode**: Outcome AND magnitude sampled together from historical P/L sequence

### Proposed Architecture

#### Two Independent Configuration Dimensions
1. **`outcome_sampling`**: How to determine if a trade wins or loses
   - `'iid'`: Use win_rate with random.random() (independent trials)
   - `'bootstrap'`: Sample win/loss outcomes from historical P/L signs (preserves win rate patterns and streaks)

2. **`magnitude_sampling`**: How to determine profit/loss amounts
   - `'generated'`: Use generate_risk()/generate_reward() with distributions
   - `'bootstrap'`: Use historical P/L values from pnl_distribution

#### Valid Combinations (4 modes)
1. **IID + Generated** (current IID mode): Independent outcomes, distribution-based magnitudes
2. **Bootstrap + Bootstrap** (current bootstrap mode): Historical outcomes and magnitudes together
3. **Bootstrap + Generated** (NEW): Historical win/loss patterns, distribution-based magnitudes
4. **IID + Bootstrap** (NEW): Independent outcomes, historical magnitudes

### Implementation Steps

- [ ] **Step 9.1:** Write tests for `sample_outcomes_bootstrap()` function
  - Test that it samples win/loss indicators (boolean or ±1) from historical P/L
  - Test that it preserves win rate from historical data
  - Test moving-blocks bootstrap with specified block_size
  - Test streak preservation (consecutive wins/losses)
  - Test with edge cases: all wins, all losses, single trade
  - Test that returned array length matches num_trades

- [ ] **Step 9.2:** Implement `sample_outcomes_bootstrap(pnl_distribution, num_trades, block_size)` in `simulator.py`
  - Extract win/loss indicators from pnl_distribution (win if pnl >= 0)
  - Apply moving-blocks bootstrap to sample outcome sequence
  - Return boolean array or ±1 array indicating win/loss for each trade
  - DRY: Consider reusing/refactoring `sample_pnl_moving_blocks()` logic
  - No fallbacks: raise ValueError if pnl_distribution is empty or invalid

- [ ] **Step 9.3:** Write tests for `sample_magnitudes_bootstrap()` function
  - Test that it samples P/L magnitudes separately from outcomes
  - Test that it returns separate win_magnitudes and loss_magnitudes arrays
  - Test moving-blocks bootstrap with specified block_size
  - Test with historical data containing only wins or only losses
  - Test edge cases: single trade, empty distribution
  - Test that magnitude signs are stripped (return absolute values)

- [ ] **Step 9.4:** Implement `sample_magnitudes_bootstrap(pnl_distribution, num_trades, block_size)` in `simulator.py`
  - Sample from pnl_distribution using moving-blocks bootstrap
  - Return array of absolute magnitudes (strip signs)
  - OR: Return two arrays (win_magnitudes, loss_magnitudes) sampled separately from wins/losses
  - DRY: Reuse moving-blocks logic, avoid duplicating bootstrap mechanics
  - Document that magnitudes will be applied with sign from outcome_sampling

- [ ] **Step 9.5:** Write tests for refactored `simulate_trades()` with new parameters
  - Test all 4 combinations: (iid/bootstrap) × (generated/bootstrap)
  - Test that IID+Generated matches current IID mode behavior exactly
  - Test that Bootstrap+Bootstrap matches current bootstrap mode behavior exactly
  - Test new Bootstrap+Generated mode: historical win rate, distribution magnitudes
  - Test new IID+Bootstrap mode: independent outcomes, historical magnitudes
  - Test that losing streaks are correctly tracked in all modes
  - Test interaction with reward_calculation_method (capping should work in all modes)
  - Verify no backward-compatibility fallbacks or silent defaults

- [ ] **Step 9.6:** Refactor `simulate_trades()` to use new architecture
  - Add parameters: `outcome_sampling='iid'`, `magnitude_sampling='generated'`
  - Remove existing `simulation_mode` parameter (breaking change requiring updates elsewhere)
  - Early in function: Call outcome/magnitude sampling functions based on parameters
  - In main loop: Combine sampled outcome with sampled/generated magnitude
  - Apply reward caps appropriately based on magnitude_sampling method
  - DRY: Extract outcome application logic to avoid duplication
  - No fallbacks: Raise ValueError for invalid parameter combinations
  - Update docstring with clear explanation of all parameters and combinations

- [ ] **Step 9.7:** Write tests for `run_monte_carlo_simulation()` parameter changes
  - Test that it accepts outcome_sampling and magnitude_sampling parameters
  - Test that it correctly passes them to simulate_trades()
  - Test that old simulation_mode parameter is removed (should raise error if used)
  - Test default values: outcome_sampling='iid', magnitude_sampling='generated'

- [ ] **Step 9.8:** Update `run_monte_carlo_simulation()` function signature
  - Replace `simulation_mode` with `outcome_sampling` and `magnitude_sampling`
  - Add defaults: `outcome_sampling='iid'`, `magnitude_sampling='generated'`
  - Pass new parameters to all `simulate_trades()` calls
  - Update docstring with examples of each combination
  - No backward compatibility: Remove simulation_mode entirely

- [ ] **Step 9.9:** Update `replay.py` if it uses simulation_mode
  - Check if replay_actual_trades() or related functions reference simulation_mode
  - Update to new parameter names if needed
  - Add tests to verify replay still works

- [ ] **Step 9.10:** Write integration tests for `app.py` with new parameters
  - Test form submission with outcome_sampling and magnitude_sampling dropdowns
  - Test session storage of new parameters for re-runs
  - Test all 4 valid combinations via form submission
  - Test that invalid combinations are rejected with clear error messages

- [ ] **Step 9.11:** Update `app.py` Flask routes
  - Replace simulation_mode handling with outcome_sampling and magnitude_sampling
  - Accept both parameters from form POST data
  - Set explicit defaults (no fallbacks to old simulation_mode)
  - Store both in session for re-runs
  - Pass both to run_monte_carlo_simulation()
  - Add validation: reject if parameters are missing or invalid

- [ ] **Step 9.12:** Update `templates/_simulation_form.html`
  - Replace single "Simulation Mode" dropdown with two separate dropdowns:
    1. "Outcome Sampling" (IID, Bootstrap)
    2. "Magnitude Sampling" (Generated, Bootstrap)
  - Add comprehensive tooltips explaining:
    - What outcome vs magnitude sampling means
    - Use cases for each combination
    - When to use bootstrap vs IID for each dimension
  - Set defaults: outcome='iid', magnitude='generated' (preserves current default behavior)
  - Add visual grouping or hint showing the 4 valid combinations

- [ ] **Step 9.13:** Update all tests to use new parameter names
  - Update test_simulator.py: Replace simulation_mode with new parameters
  - Update test_app.py: Replace simulation_mode with new parameters
  - Update test_integration.py: Test all 4 combinations
  - Ensure no tests use old simulation_mode parameter
  - Run full test suite: `tm_trade_analyzer_venv/bin/pytest -v`

- [ ] **Step 9.14:** Update documentation
  - Update README.md: Replace simulation_mode with outcome/magnitude_sampling
  - Add examples showing when to use each combination
  - Update CLI help text if CLI still exists (monte_carlo_trade_sizing.py)
  - Add clear migration notes for any external users of the API

- [ ] **Step 9.15:** Final validation and cleanup
  - Run full test suite: `tm_trade_analyzer_venv/bin/pytest -v`
  - Manually test all 4 combinations in web UI
  - Verify results are intuitive and correct for each mode
  - Verify no old simulation_mode references remain in codebase
  - Search for any TODO comments added during implementation
  - Verify DRY principle: no duplicated outcome/magnitude logic

### DRY Principles to Follow
- **Extract moving-blocks logic**: Create shared helper for bootstrap block sampling (avoid duplication in outcome vs magnitude functions)
- **Extract outcome application**: Single function to apply outcome + magnitude → realized P/L
- **No duplicated validation**: Validate parameters once at entry point, not in every helper

### No Fallbacks / Explicit Errors
- **No silent defaults**: If parameters are missing, raise ValueError with clear message
- **No backward compatibility**: Remove simulation_mode entirely, don't map it to new parameters
- **Validate combinations**: Reject invalid parameter values immediately
- **Clear error messages**: Explain what went wrong and what valid options are

### Testing Focus
- **Exact behavior preservation**: IID+Generated must match old IID mode exactly
- **Exact behavior preservation**: Bootstrap+Bootstrap must match old bootstrap mode exactly
- **New combinations work correctly**: Bootstrap+Generated and IID+Bootstrap produce sensible results
- **Streak tracking**: Verify losing streaks tracked correctly in all 4 modes
- **Reward capping**: Verify caps apply correctly with magnitude_sampling='generated' (not bootstrap)
- **Edge cases**: Empty data, single trade, all wins, all losses

## Phase 10: Data Quality Improvements & Validation

### Part A: Critical Data Alignment Bug Fix ✅
Fixed P/L/date misalignment caused by alphabetical sorting in trade_parser.py. Added `sort=False` to all groupby operations for consistency. Verified alignment with real data and existing tests.

### Part B: Fix Template Display for Multi-Contract (PRIORITY 1 - Important)
- [ ] **Step 10.4:** Write test for replay table P/L percentage calculation with multiple contracts
  - Test with 1 contract, 2 contracts, and 5 contracts
  - Verify percentage remains constant regardless of contract count
  - Verify calculation: `(pnl_per_contract / theoretical_risk_per_spread) * 100`

- [ ] **Step 10.5:** Fix P/L % calculation in `templates/results.html`
  - Change: `(trade.total_pnl / trade.theoretical_risk) * 100`
  - To: `(trade.pnl_per_contract / trade.theoretical_risk) * 100`
  - Update tooltip to clarify it's P/L per spread, not total P/L

- [ ] **Step 10.6:** Verify fix doesn't break existing tests
  - Run `tm_trade_analyzer_venv/bin/pytest tests/test_integration.py -v`
  - Manually test in browser with various contract counts

#### Part C: Data Quality Warnings (PRIORITY 2 - High Value)
- [ ] **Step 10.7:** Write tests for data validation in `trade_parser.py`
  - Test detection of missing closing prices
  - Test detection of losses exceeding theoretical max (with 5% commission buffer)
  - Test detection of gains exceeding theoretical max + spread width (impossible)
  - Test that validation returns warnings list with trade identifiers

- [ ] **Step 10.8:** Implement data validation in `trade_parser.py`
  - Add `validate_trade_data()` function that checks for:
    - Missing closing prices (blank 'Trade Price' field)
    - Losses > theoretical_max_loss * 1.05 (5% buffer for commissions)
    - Gains > theoretical_max_gain + spread_width (physically impossible)
  - Return list of warnings with: trade_date, expiration, issue_type, details
  - Add field `data_quality_warnings` to stats dictionary returned by `parse_trade_csv()`

- [ ] **Step 10.9:** Write integration tests for warning display in app
  - Test that warnings are passed to template
  - Test that warnings are displayed in UI
  - Test with CSV files having known data issues

- [ ] **Step 10.10:** Update `app.py` to pass warnings to template
  - Extract `data_quality_warnings` from trade_stats
  - Pass to results template as separate variable
  - Flash warnings to user if any critical issues found

- [ ] **Step 10.11:** Update `templates/results.html` to display warnings
  - Add "Data Quality Warnings" section above replay table (if warnings exist)
  - Use warning/alert styling (yellow/orange background)
  - List each warning with trade date, issue type, and recommendation
  - Add option to "Show only clean trades" (future enhancement)

## Phase 11: Process Improvements - Prevent Data Corruption Bugs
**Goal:** Improve testing and development practices to prevent critical bugs like the P/L/date misalignment from reaching production.

**Root Cause Analysis:**
1. **Insufficient test data validation**: Tests check lengths and types but not actual values
2. **Synthetic test data hides bugs**: Simple alphabetically-sortable test data doesn't expose sorting issues
3. **No end-to-end value validation**: Integration tests check page loads but not correctness of specific trade calculations
4. **Missing known-value tests**: No tests that verify "trade X should have P/L Y"

### Steps
- [ ] **Step 11.1:** Add data validation requirements to copilot instructions
  - Tests must verify actual values, not just structure
  - Tests must use real data that exposes edge cases (alphabetical sorting, date formatting, etc.)
  - Integration tests must include "golden file" comparisons for known trades
  - Any groupby operation must explicitly set sort parameter

- [ ] **Step 11.2:** Create "golden file" test fixtures
  - Select 5-10 specific trades from real CSV files
  - Document expected values: date, P/L, risk, reward, percentage
  - Create test that parses real file and verifies these exact values
  - Update fixture when intentionally changing calculation logic

- [ ] **Step 11.3:** Add data integrity checks to trade_parser
  - Validate that dates are in chronological order after parsing
  - Add assertions that all per-trade lists have same length
  - Add warnings if dates are out of order (suggests sorting bug)
  - Return metadata about data quality to help debugging

- [ ] **Step 11.4:** Improve test coverage for edge cases
  - Test with unsorted expirations (alphabetically different from chronological)
  - Test with duplicate expirations
  - Test with missing data in various combinations
  - Test parsing output consistency: verify same data different ways

- [ ] **Step 11.5:** Add automated checks before commits
  - Consider pre-commit hook that runs key tests with real data
  - Flag any groupby without explicit sort parameter
  - Verify test files include at least one real data file test

### Success Criteria
- [ ] Tests verify actual calculated values, not just structure
- [ ] All tests use realistic data that could expose hidden bugs
- [ ] Integration tests include known-value verification
- [ ] Copilot instructions updated with testing requirements
- [ ] No groupby operations without explicit sort parameter
- [ ] Real data test files committed to repository

#### Part D: Improved Handling of Missing Prices (PRIORITY 3 - Nice to Have)
- [ ] **Step 10.12:** Write tests for theoretical risk estimation when prices missing
  - Test that risk can be back-calculated from P/L when closing prices absent
  - Test that estimation includes commission buffer
  - Test fallback behavior when neither prices nor P/L available

- [ ] **Step 10.13:** Implement smarter risk estimation in `trade_parser.py`
  - When closing prices missing but P/L present, use P/L to estimate actual risk
  - For missing prices: `estimated_risk = max(abs(pnl), opening_debit)`
  - Mark estimated values with flag for transparency
  - Update documentation to explain estimation methodology

#### Part E: Alpaca Data Integration (PRIORITY 4 - Future Enhancement)
**Note:** This is a larger effort and not needed immediately. Consider only if data quality issues are severe across many files.

- [ ] **Step 10.14:** Research Alpaca API for historical options data
  - Investigate data availability (date ranges, symbols, strikes)
  - Check if free tier provides sufficient access
  - Document API rate limits and data limitations
  - Assess data quality vs trading platform exports

- [ ] **Step 10.15:** Design backfill architecture
  - Create separate tool/module for data enrichment (not in main flow)
  - Read CSV, identify missing prices, query Alpaca API, write enriched CSV
  - Keep original CSV unchanged, create new file with "_enriched" suffix
  - Add validation to compare Alpaca prices vs reported P/L

- [ ] **Step 10.16:** Implement proof-of-concept for one trade
  - Successfully fetch historical option price for specific contract
  - Match against CSV data
  - Validate P/L calculation accuracy
  - Document findings and decide on full implementation

### Success Criteria
- [ ] **CRITICAL**: P/L values align with correct dates (2020-07-28 shows 73.9%, not 301%)
- [ ] **CRITICAL**: Chronological order preserved from CSV file 
- [ ] All existing tests pass with corrected data alignment
- [ ] Replay table shows correct P/L percentages for multi-contract scenarios
- [ ] Users see clear warnings for trades with data quality issues  
- [ ] Documentation explains how to handle missing/suspicious data
- [ ] Test coverage includes real-data validation (not just synthetic test data)
- [ ] No regressions in existing functionality

## Additional Completed Tasks
- [X] **Testing:** Added comprehensive test suite including unit tests for web app functionality and end-to-end integration test with real data.
- [X] **Re-run functionality:** Implemented ability to change options after results and re-run simulation without re-uploading CSV.
- [X] **Risk method consistency:** Fixed percent-sizing planning to respect selected `risk_calculation_method`, corrected Nuclear semantics to use max theoretical loss consistently across simulator/UI/README, and updated simulator tests accordingly.
- [X] **Risk method UX update:** Added `Variable`/`Fixed` prefixes in the UI selector, introduced separate fixed methods for conservative theoretical max and theoretical max, widened selector width for readability, and added/updated tests.
- [X] **Historical trade replay:** Implemented feature to show actual trade performance using the same position sizing settings as Monte Carlo simulation, displayed alongside simulation results for comparison.
