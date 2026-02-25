# TM Trade Analyzer

A Monte Carlo simulation tool for analyzing TradeMachine backtested trades. This web application helps traders understand the risk and reward characteristics of their trading strategies by running thousands of simulated trading scenarios.

## Features

- **Monte Carlo Simulation**: Run thousands of simulated trading scenarios to understand potential outcomes
- **Position Sizing Analysis**: Test different position sizes and risk percentages
- **Risk Metrics**: Analyze bankruptcy probability, maximum drawdown, and losing streaks
- **Multiple Simulation Modes**: Choose between independent trades (IID) or bootstrap sampling that preserves historical patterns
- **Dynamic Risk Sizing**: Option to adjust position sizes based on current account balance
- **Web Interface**: Easy-to-use web application for uploading trade data and viewing results

## Installation

### Prerequisites

- Python 3.8 or higher
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

## Getting Trade Data from TradeMachine

To use this analyzer, you need to export your backtested trade data from TradeMachine as a CSV file. Follow these steps:

### Step 1: Open TradeMachine and Load Your Strategy

Launch TradeMachine and open the strategy you want to analyze.

### Step 2: Run Backtesting

Execute your backtest to generate trade results.

### Step 3: Export Trade Data

1. Navigate to the trade results or performance report section
2. Look for an "Export" or "Download" option
3. Select CSV format for the trade data

![TradeMachine Export Options](Screenshot%202026-02-24%20at%2010.44.11 PM.png)

### Step 4: Verify CSV Format

Ensure your CSV file contains the required columns for proper analysis:
- Date
- Description (containing "Open" for opening legs)
- Profit/Loss
- Trade Price
- Size
- Strike
- Expiration

![Sample CSV Structure](Screenshot%202026-02-24%20at%2010.44.26 PM.png)

## Running the Application

### Method 1: Using Flask CLI (Recommended)

1. **Set Flask environment variables** (optional but recommended):
   ```bash
   export FLASK_APP=app.py
   export FLASK_ENV=development
   ```

2. **Run the application**:
   ```bash
   flask run
   ```

### Method 2: Direct Python execution

```bash
python app.py
```

### Method 3: Using the virtual environment Python

```bash
tm_trade_analyzer_venv/bin/python app.py
```

The application will start and be available at `http://127.0.0.1:5001/`

## Usage

1. **Open your browser** and navigate to `http://127.0.0.1:5001/`

2. **Upload your CSV file** containing the TradeMachine backtest data

3. **Configure simulation parameters**:
   - **Initial Balance**: Starting account balance for simulations
   - **Number of Simulations**: How many Monte Carlo runs to perform (1000+ recommended)
   - **Option Commission**: Commission per contract
   - **Position Sizing Mode**:
     - **Dynamic Percent**: Adjusts contract count to maintain target risk percentage
     - **Fixed Percent**: Uses fixed risk percentages with static contract counts
     - **Fixed Contracts**: Uses predetermined contract counts
   - **Risk Calculation Method**:
       - **Variable: Conservative Theoretical Max**: Variable losses up to 95th percentile of theoretical losses (most conservative cap)
       - **Variable: Theoretical Max**: Variable losses up to maximum theoretical loss
       - **Fixed: Median Realized**: Fixed loss amount at median of actual historical losses
       - **Fixed: Average Realized**: Fixed loss amount at average of actual historical losses
       - **Fixed: Average Realized (Trimmed)**: Fixed loss amount at average excluding top 5% outliers
       - **Fixed: Conservative Theoretical Max**: Fixed loss amount at conservative theoretical max
       - **Fixed: Theoretical Max**: Fixed loss amount at theoretical max
   - **Simulation Mode**:
     - **IID (Independent Identical Distribution)**: Each trade is independent
     - **Moving Block Bootstrap**: Preserves historical streak patterns
   - **Block Size**: Size of trade blocks for bootstrap sampling

4. **Run Simulation** and view the results table showing:
   - Average final balance
   - Bankruptcy probability
   - Maximum drawdown statistics
   - Losing streak analysis

5. **Adjust parameters** and re-run simulations without re-uploading the CSV

## Understanding the Results

### Key Metrics

- **Avg Final $**: Average account balance after all simulations
- **Bankruptcy Prob**: Percentage of simulations where account reached zero
- **Avg Max Drawdown**: Average of the worst drawdown in each simulation
- **Max Drawdown**: Worst drawdown across all simulations
- **Avg Max Losing Streak**: Average length of longest losing streak
- **Max Losing Streak**: Longest losing streak in any simulation

### Position Sizing Modes

- **Percent Mode**: Tests different risk percentages of your account balance
- **Contracts Mode**: Tests different fixed contract counts per trade

### Simulation Modes

- **IID**: Assumes each trade is independent with no streak patterns
- **Bootstrap**: Uses historical trade sequences to maintain realistic patterns

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
