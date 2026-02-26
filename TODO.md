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

## Additional Completed Tasks
- [X] **Testing:** Added comprehensive test suite including unit tests for web app functionality and end-to-end integration test with real data.
- [X] **Re-run functionality:** Implemented ability to change options after results and re-run simulation without re-uploading CSV.
- [X] **Risk method consistency:** Fixed percent-sizing planning to respect selected `risk_calculation_method`, corrected Nuclear semantics to use max theoretical loss consistently across simulator/UI/README, and updated simulator tests accordingly.
- [X] **Risk method UX update:** Added `Variable`/`Fixed` prefixes in the UI selector, introduced separate fixed methods for conservative theoretical max and theoretical max, widened selector width for readability, and added/updated tests.
- [X] **Historical trade replay:** Implemented feature to show actual trade performance using the same position sizing settings as Monte Carlo simulation, displayed alongside simulation results for comparison.
