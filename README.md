# TradeMachine Trade Analyzer

A trade analysis tool for TradeMachine backtested strategies. Upload a CSV export and instantly see a trade-by-trade historical replay with position sizing applied — showing exactly how a strategy would have performed with compounding. Optionally run Monte Carlo simulations to project future outcomes, test different position sizes, and understand bankruptcy risk and drawdown characteristics. (**Warning:** Monte Carlo has known bugs, notably with false negative bankruptcy risk, and shouldn't be taken seriously.)

## Features

- **Trade Replay**: Replay your historical trades with position sizing and compounding applied, showing exactly how your account would have grown or declined trade by trade
- **Trade-by-Trade Drilldown**: Hover over any trade in the replay table to see the actual opening/closing legs, P/L, and theoretical risk for that specific trade
- **Overlapping Trade Detection**: Identifies and handles trades that were open simultaneously, correctly accounting for concurrent risk exposure
- **Position Sizing Analysis**: Test different position sizes and risk percentages, with dynamic sizing that adjusts contract counts as your account balance changes
- **Monte Carlo Simulation** *(optional)*: Run thousands of simulated trading scenarios to understand potential future outcomes, bankruptcy risk, and drawdown characteristics
- **Multiple Simulation Modes**: Choose between independent trades (IID) or bootstrap sampling that preserves historical streak patterns
- **Interactive Charts**: Visualize account balance trajectories with percentile bands, compare Monte Carlo projections to actual historical replay
- **Web Interface**: Easy-to-use web application for uploading trade data and viewing results

## Installation

### Prerequisites

- Python 3.11.9 or higher
- pip (Python package installer)

### Setup

1. **Clone or download the repository**
   ```bash
   git clone <repository-url>
   cd tm_trade_analyzer
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv tm_trade_analyzer_venv
   ```

3. **Activate the virtual environment**
   - On macOS/Linux:
     ```bash
     source tm_trade_analyzer_venv/bin/activate
     ```
   - On Windows:
     ```bash
     tm_trade_analyzer_venv\Scripts\activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   python app.py
   ```
   The application will start and be available at `http://127.0.0.1:5001/`

## Getting Trade Data from TradeMachine

To use this analyzer, you need to export your backtested trade data from TradeMachine as a CSV file. 
**Important** This tool has only been tested on Long Call debit spreads. Any other trade type is likely to break it!!
Follow these steps:

1. From the backtesting results, click on the main results summary to open a popup with showing trade details
![TradeMachine Export Options](Screenshot%202026-02-24%20at%2010.44.11 PM.png)

2. Click "Download" to get a CSV file. 
![Sample CSV Structure](Screenshot%202026-02-24%20at%2010.44.26 PM.png)

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_simulator.py
pytest tests/test_trade_parser.py
pytest tests/test_app.py

# Run with coverage
pytest --cov=simulator --cov=trade_parser
```

### Project Structure

```
tm_trade_analyzer/
├── app.py                 # Flask web application
├── simulator.py           # Monte Carlo simulation logic
├── trade_parser.py        # CSV parsing and statistics calculation
├── requirements.txt       # Python dependencies
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   └── results.html
├── static/                # CSS, JS, images
├── tests/                 # Unit and integration tests
├── uploads/               # Temporary uploaded files (gitignored)
└── README.md             # This file
```

## License

See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request
