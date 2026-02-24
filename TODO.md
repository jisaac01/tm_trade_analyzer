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
- [ ] **Step 5.3:** Add a loading spinner/overlay on the frontend using simple JavaScript. Monte Carlo simulations can take a few seconds, so visual feedback is critical for a quality product.
- [ ] **Step 5.4:** (Optional but recommended) Move the simulation processing into a background thread or use AJAX/Fetch API to prevent the browser from timing out or appearing frozen during heavy calculations.

## Additional Completed Tasks
- [X] **Testing:** Added comprehensive test suite including unit tests for web app functionality and end-to-end integration test with real data.
- [X] **Re-run functionality:** Implemented ability to change options after results and re-run simulation without re-uploading CSV.
