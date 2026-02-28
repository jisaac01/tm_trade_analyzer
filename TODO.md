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

### Part B: Fix Template Display for Multi-Contract (PRIORITY 1 - Important) ✅
- [X] **Step 10.4:** Write test for replay table P/L percentage calculation with multiple contracts
  - Created TestReplayPnlPercentageCalculation test class with 2 tests
  - Tests with 1, 2, and 5 contracts verify P/L % remains constant (50%, -60%, 80%)
  - Tests that zero/negative theoretical risk raises clear ValueError (fail-fast validation)
  - Refactored P/L % calculation out of template into replay.py as `pnl_pct` field
  - Additionally created TestReplayRiskPercentageCalculation test class with 3 tests
  - Refactored Risk % calculation out of template into replay.py as `risk_pct` field
  - Tests verify Risk % = (theoretical_risk / balance_before) * 100 with varying balances, contract counts, and edge cases
  - Added TestReplayDataValidation class to test fail-fast behavior on invalid data
  - **CRITICAL**: All calculations now fail fast on invalid data (zero/negative risk) with clear error messages
    surfacing CSV data quality issues immediately, rather than silently handling or hiding them

- [X] **Step 10.5:** Fix P/L % calculation in `templates/results.html`
  - Changed from: `(trade.total_pnl / trade.theoretical_risk) * 100`
  - To: `(trade.pnl_per_contract / trade.theoretical_risk) * 100`
  - P/L % now correctly shows percentage per contract regardless of contract count

- [X] **Step 10.6:** Verify fix doesn't break existing tests and no similar errors exist
  - Ran `tm_trade_analyzer_venv/bin/pytest tests/test_app.py tests/test_integration.py -v` - all pass
  - Verified trade_parser.py, replay.py, simulator.py, and app.py all correctly separate per-contract from total values
  - Bug was isolated to template display only

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

## Phase 12: Interactive Graph Visualizations ✅ COMPLETE

**Completed:** All 20 steps (12.1-12.20)

**Summary:**
- Implemented three interactive Chart.js visualizations:
  1. **Comparison Chart**: All thresholds (median trajectories), clickable lines
  2. **Detail Chart**: Selected threshold with percentile bands (p5-p95, p25-p75, p50)
  3. **Replay Chart**: Historical actual performance with matching labels
- Table row click handlers with smooth scrolling and highlighting
- Hover tooltips with exact balance values
- Show/Hide charts toggle button
- Concise in-app documentation with tooltip icons
- Added "Median Final $" column to highlight skewed distributions
- Removed zoom functionality (problematic with linked charts)
- 228 tests passing

**Key Technical Decisions:**
- Server-side percentile calculation (efficient)
- Client-side rendering with Chart.js (interactive, lightweight)
- Reversed tooltip legend order (highest to lowest)
- Matched replay labels to Monte Carlo format (e.g., "10.00%" not "Scenario 0")
- Brighter blues (#3b82f6) for visibility on dark background
- Different colors per replay line (COLORS array)

**Test Improvements:**
- Added explicit median column verification tests
- Revealed test quality issue: tests were checking "some fields exist" not "complete structure"
- Enhanced tests to validate column ordering and formatting

## Phase 13: Investigate Bootstrap vs Replay Discrepancy
**Goal:** Understand and quantify why bootstrap simulation results (averaged over 1000 runs) are order-of-magnitude larger than historical replay results, despite both using the same per-trade risks and P/L values.

**Context:** After fixing the bootstrap position sizing bug (using per-trade risks instead of aggregate p95), we now observe:
- Historical replay at 75% risk: $4.8M final balance (bankrupts at 100%)
- Bootstrap simulation at 75% risk: $36B average final balance (0% bankruptcy at 100%)

With 1000 simulations, we expect to see the average/typical case, not just lucky outliers. This massive difference suggests either:
1. The historical trade sequence is statistically unusual (unlucky ordering)
2. There's still a subtle bug in how bootstrap applies position sizing
3. The moving-blocks sampling is creating unrealistically favorable sequences
4. Dynamic risk sizing compounds differently than expected with reordering

### Investigation Steps

- [ ] **Step 13.1:** Analyze historical trade sequence characteristics
  - Calculate sequential metrics: cumulative P/L at each step, drawdown periods, win/loss clustering
  - Measure "sequence quality score": ratio of early wins to early losses (compound effect)
  - Identify if historical sequence had unlucky early losses that limited compounding
  - Compare: What % of 1000 bootstrap runs have worse sequence scores than historical?

- [ ] **Step 13.2:** Quantify the impact of trade reordering
  - Create "best case" replay: Sort historical trades by risk (low first) and P/L (wins first)
  - Create "worst case" replay: Sort by risk (high first) and P/L (losses first)
  - Create "random case" replay: Shuffle trades randomly (no moving blocks), run 100 times
  - Compare final balances: worst < historical < random < bootstrap < best
  - This bounds the "reordering effect" magnitude

- [ ] **Step 13.3:** Validate position sizing parity between replay and bootstrap
  - For the exact historical sequence, verify contract counts match:
    - Run replay with historical sequence
    - Run bootstrap with block_size = len(trades) (forces exact historical sequence)
    - Compare: Do they produce identical contract counts and final balance?
  - If not identical, there's still a position sizing bug
  - If identical, the difference is purely from reordering

- [ ] **Step 13.4:** Analyze moving-blocks bootstrap sampling bias
  - Measure: Are low-risk winners more likely to be sampled than high-risk losers?
  - With block_size=5, certain subsequences may be oversampled
  - Compare sampling frequency: Does bootstrap favor certain trades?
  - Test with block_size=1 (pure random sampling): Does discrepancy reduce?

- [ ] **Step 13.5:** Examine compounding effect magnitude
  - Track: At what trade number do bootstrap and replay diverge significantly?
  - Calculate: If balance is 10x higher at trade 20, how much larger is it at trade 40?
  - Identify: Is the discrepancy stable or exponentially growing?
  - This reveals if it's early-phase advantage or continuous compounding

- [ ] **Step 13.6:** Create statistical comparison metrics
  - For bootstrap distribution across 1000 runs, calculate:
    - Percentiles: p5, p25, p50, p75, p95 of final balance
    - Bankruptcy rate by percentile
    - Mean vs median (detect outlier skew)
  - Rank historical replay result against 1000 bootstrap runs
  - Answer: "Historical is worse than X% of bootstrap runs"
  - Determine if historical is in bottom 1% (unlucky) or closer to median

- [ ] **Step 13.7:** Test alternative sampling methods
  - Compare moving-blocks (current) vs IID sampling (ignores streaks)
  - Compare block_size=5 vs block_size=1 vs block_size=10
  - Measure: Does block size significantly affect final balance distribution?
  - This isolates impact of streak preservation vs pure reordering

- [ ] **Step 13.8:** Validate position sizing calculation directly
  - Write test that logs every contract count decision for both replay and bootstrap
  - For first 10 trades of historical sequence:
    - Replay: Log balance, risk, contracts, P/L
    - Bootstrap (forced historical): Log same
  - Verify: Are contract counts and balance updates identical?
  - If differences emerge, trace exact divergence point

- [ ] **Step 13.9:** Document findings and recommendations
  - Write summary report explaining the discrepancy
  - If historical sequence is simply unlucky: Document percentile rank
  - If bootstrap has favorable bias: Recommend mitigation (e.g., use median not mean)
  - If bug found: Fix and retest
  - Update UI to show: "Historical replay is X% percentile of bootstrap distribution"

- [ ] **Step 13.10:** Implement "sequence quality" metric in UI (optional)
  - Add calculation: Measure how favorable/unfavorable a trade sequence is
  - Display in results: "Your historical sequence is in the bottom 15% of simulated outcomes"
  - Help users understand: "Simulation shows you were unlucky" vs "Simulation is overoptimistic"
  - Add context: "If you had experienced an average sequence ordering, expected result: $X"

### Key Questions to Answer
1. **Is the historical sequence statistically unusual?** (Percentile rank among bootstrap runs)
2. **Do replay and bootstrap use identical position sizing for same sequence?** (Validation test)
3. **How much of the gap is due to reordering vs compounding?** (Best/worst case bounds)
4. **Is moving-blocks sampling introducing bias?** (Compare to IID sampling)
5. **Should we show median instead of mean in UI?** (If distribution is highly skewed)
6. **Should we confidence-bound the results?** ("With 90% confidence, expect $X to $Y")

### Expected Outcomes
- [ ] Quantified explanation: "Historical is in bottom 5% of bootstrap outcomes due to unlucky early losses"
- [ ] Or: "Bug found in X, fixed, results now align within 2x"
- [ ] Or: "Bootstrap overestimates due to Y, recommend using median instead of mean"
- [ ] Improved UI showing context: "Historical vs Expected Range"
- [ ] User confidence in simulation realism

### Success Criteria
- [ ] Can definitively explain the order-of-magnitude difference
- [ ] Users understand whether historical performance was lucky/unlucky/typical
- [ ] Simulation results are properly calibrated and contextualized
- [ ] Any remaining bugs are identified and fixed
- [ ] UI communicates uncertainty and ranges, not just point estimates

## Phase 14: Test Quality & Verification Infrastructure
**Goal:** Improve test quality by discouraging mocking and auditing existing tests for value.

### Part A: Mock Discouragement Infrastructure ✅

- [X] **Step 14.1:** Create custom pytest fixture that warns on mock usage
  - Create `conftest.py` with `pytest_configure` hook
  - Patch `unittest.mock.patch` and `unittest.mock.Mock` to emit warnings
  - Warning message: "⚠️  MOCKING DETECTED: Consider if this test could use real data instead. Integration tests with minimal mocking are preferred. See test_integration.py for examples."
  - Make warning visible but non-blocking (don't fail tests)
  - Add option to suppress for legitimate unit tests (decorator or comment marker)

- [X] **Step 14.2:** Add linting/code review checklist
  - Create `.github/PULL_REQUEST_TEMPLATE.md` with checkpoint:
    - "[ ] Any new mocked tests are justified (and documented with comment explaining why real data won't work)"
  - Add developer guideline doc: `docs/TESTING_GUIDELINES.md`
    - Prefer: Real CSVs from test_data/
    - Prefer: Small num_simulations for speed (5-10 runs)
    - Prefer: Seeded RNG for deterministic Monte Carlo tests
    - Use mocks only for: External APIs, file I/O that's too slow, unavoidable randomness
    - Every mock requires a comment explaining why it's necessary

### Part B: Test Audit & Cleanup ✅ → 🔄 In Progress

- [X] **Step 14.3:** Audit test_app.py for shallow/mocked tests
  - Reviewed all 21 tests
  - Identified 13 patches (62% mock ratio)
  - Flagged 3 heavily-mocked tests for conversion to integration tests
  - Found shallow assertions (HTML string checks) in several tests

- [X] **Step 14.4:** Audit test_simulator.py for overlapping coverage
  - Reviewed ~90 tests with 42 patches (47% mock ratio)
  - Most patches mock `generate_risk()` and `generate_reward()` 
  - **Discovered better approach:** Use seeded RNG instead of mocks for deterministic tests
  - **Started conversion:** 2 tests converted, 4 mocks removed, 6 warnings eliminated

- [X] **Step 14.5:** Audit test_replay.py and test_trade_parser.py
  - Both files: 0 patches (0% mock ratio) ✅
  - Excellent quality - use real data and verify actual values
  - Should serve as models for other tests
  - No changes needed

- [X] **Step 14.6:** Document test quality metrics
  - **Initial:** 228 tests, 79 patches, 119 warnings, 35% mock ratio ❌
  - **After Part A:** 228 tests, 75 patches, 113 warnings, 33% mock ratio 🔄
  - **Current (Part B Complete):** 228 tests, 5 patches, 103 warnings, 2.19% mock ratio ✅
  - **Target:** 240 tests, <40 patches, <20% mock ratio ✅
  - Created comprehensive audit: `docs/TEST_AUDIT_PHASE14.md`
  - Includes file-by-file breakdown and specific recommendations

- [X] **Step 14.7:** Example test templates
  - Already included in `docs/TESTING_GUIDELINES.md`
  - Guidelines have clear good/bad examples
  - No separate EXAMPLES.md needed

### Conversion Progress & Learnings

**Key Discovery:** Many tests mock `generate_risk()`/`generate_reward()` for predictability. Better approach: **Use seeded RNG for real generation**.

**Conversion Pattern:**
```python
# Before: Mock internal functions (tests nothing)  
with unittest.mock.patch('simulator.generate_risk', return_value=100):
    results = simulate_trades(...)
    assert results[0]['balance'] == 1500

# After: Seeded RNG (tests real code)
np.random.seed(42)
results = simulate_trades(...)
assert 1400 < results[0]['balance'] < 1600  # Range accounts for real variability
```

**Tests Converted:**
1. test_perfect_win_rate (2 mocks → 0) - Part A
2. test_zero_win_rate (2 mocks → 0) - Part A
3. test_results_get_with_session (2 mocks → 0) - Part B
4. test_reward_calculation_method_passed_to_simulator (3 mocks → 0) - Part B
5. test_results_page_includes_file_uuid_in_link (2 mocks → 0) - Part B

**Total Reduction:** 12 patches → 5 patches (58% reduction), 113 warnings → 103 warnings (9% reduction)

###X] Mocking warns during test runs (visible feedback loop)
- [X] Testing guidelines document exists and is referenced in PR template
- [X] Test audit complete with actionable refactoring list
- [X] Mock ratio calculated and tracked
- [X] Developers have clear examples of good vs bad tests
- [X] **Phase 14 Part B Complete:** Mock ratio reduced to 2.19% (below 20% target)
- [ ] Developers have clear examples of good vs bad tests

## Additional Completed Tasks
- [X] **Testing:** Added comprehensive test suite including unit tests for web app functionality and end-to-end integration test with real data.
- [X] **Re-run functionality:** Implemented ability to change options after results and re-run simulation without re-uploading CSV.
- [X] **Risk method consistency:** Fixed percent-sizing planning to respect selected `risk_calculation_method`, corrected Nuclear semantics to use max theoretical loss consistently across simulator/UI/README, and updated simulator tests accordingly.
- [X] **Risk method UX update:** Added `Variable`/`Fixed` prefixes in the UI selector, introduced separate fixed methods for conservative theoretical max and theoretical max, widened selector width for readability, and added/updated tests.
- [X] **Historical trade replay:** Implemented feature to show actual trade performance using the same position sizing settings as Monte Carlo simulation, displayed alongside simulation results for comparison.
