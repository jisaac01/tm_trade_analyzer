# TODO - Active Tasks

**Note:** Completed tasks are archived in [docs/archive/TODO.md](docs/archive/TODO.md)

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

### Part C: Data Quality Warnings (PRIORITY 2 - High Value)
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

### Part D: Improved Handling of Missing Prices (PRIORITY 3 - Nice to Have)
- [ ] **Step 10.12:** Write tests for theoretical risk estimation when prices missing
  - Test that risk can be back-calculated from P/L when closing prices absent
  - Test that estimation includes commission buffer
  - Test fallback behavior when neither prices nor P/L available

- [ ] **Step 10.13:** Implement smarter risk estimation in `trade_parser.py`
  - When closing prices missing but P/L present, use P/L to estimate actual risk
  - For missing prices: `estimated_risk = max(abs(pnl), opening_debit)`
  - Mark estimated values with flag for transparency
  - Update documentation to explain estimation methodology

### Part E: Alpaca Data Integration (PRIORITY 4 - Future Enhancement)
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
- [ ] Users see clear warnings for trades with data quality issues  
- [ ] Documentation explains how to handle missing/suspicious data
- [ ] No regressions in existing functionality

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

## Future Enhancement Ideas (Optional, Not Scheduled)

These ideas were identified during Phase 15 investigation but are NOT currently required:

### Additional Test Coverage (from TEST_COVERAGE_ANALYSIS.md)
- **Phase 2-5 numeric tests:** Additional test matrices for less-common parameter combinations
  - Risk method differences tests (5-7 tests)
  - Reward cap validation tests (6-8 tests)
  - All tests already have good coverage, these would be redundant verification
- **Total potential:** 37-50 additional tests covering edge cases

**Priority:** Low - Current 244 tests provide excellent coverage

### Position Sizing Display Enhancement
- Show "sequence quality score" in UI comparing historical replay percentile vs bootstrap distribution
- Help users understand if their historical sequence was lucky/unlucky/typical
- From Phase 13 investigation (not yet started)

**Priority:** Low - Nice-to-have for user education

### Performance Optimization (Phase 5 Step 5.4)
- Move simulation processing to background thread
- Use AJAX/Fetch API for async results loading
- Prevent browser timeout on heavy simulations

**Priority:** Low - Current performance is acceptable for typical use cases

