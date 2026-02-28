# Testing Guidelines

## Philosophy

**Write tests that give high confidence in correctness, not just coverage.**

Our testing strategy prioritizes integration tests with real data over unit tests with mocks. This approach:
- Catches bugs that mocks would miss (data parsing, alignment, edge cases)
- Tests actual behavior, not implementation details
- Provides confidence that the system works end-to-end
- Is often simpler to write and maintain

## Testing Priorities

### 1. Integration Tests (Highest Value) ✅

**Prefer:** Full end-to-end tests with real CSV files and minimal/no mocking.

```python
# GOOD: Integration test with real data
def test_simulation_with_real_trades():
    csv_path = "tests/test_data/sample_trades.csv"
    trade_stats = parse_trade_csv(csv_path)
    
    result = run_monte_carlo_simulation(
        trade_stats=trade_stats,
        initial_balance=10000,
        num_simulations=10,  # Keep small for speed
        random_seed=42  # Deterministic results
    )
    
    # Verify actual values, not just structure
    assert result['median_final_balance'] > 9000
    assert result['bankruptcy_probability'] < 0.5
    assert len(result['percentile_trajectories']) == 5
```

**Why this is better:**
- Tests real parsing logic (dates, P/L, risk calculation)
- Tests actual simulation math
- Tests data flow through entire system
- Small num_simulations keeps tests fast
- Seed makes results deterministic

### 2. Pure Function Unit Tests ✅

**Prefer:** Unit tests for pure functions (no I/O, deterministic).

```python
# GOOD: Pure function test - no mocking needed
def test_get_max_risk_per_spread():
    trade = {
        'conservative_theoretical': 180,
        'theoretical_max_loss': 220
    }
    
    # Test each calculation method
    assert get_max_risk_per_spread(trade, 'conservative_theoretical') == 180
    assert get_max_risk_per_spread(trade, 'max_theoretical') == 220
```

**Why this is better:**
- No mocks needed - pure function with dictionaries
- Tests actual calculation logic
- Fast and deterministic
- Easy to add edge cases

### 3. Mocked Tests (Use Sparingly) ⚠️

**Only when:** Testing external dependencies or truly unavoidable I/O.

```python
# ACCEPTABLE: Mocking external API (with justification)
@suppress_mock_warnings  # External Alpaca API - no test data available
def test_api_error_handling():
    with patch('alpaca.get_option_price') as mock_api:
        mock_api.side_effect = ConnectionError("API unavailable")
        
        result = enrich_csv_with_prices("trades.csv")
        
        assert result['missing_prices'] > 0
        assert 'API error' in result['warnings'][0]
```

**When mocking IS appropriate:**
- External APIs (Alpaca, web services)
- File system operations that would be too slow
- Database connections
- Time-dependent behavior (datetime.now)

**When mocking is NOT appropriate:**
- Internal functions (simulator.py, trade_parser.py)
- Business logic
- Data transformations
- Calculations

## Anti-Patterns to Avoid

### ❌ Heavy Mocking of Internal Functions

```python
# BAD: Mocking our own code
@patch('simulator.calculate_balance')
@patch('trade_parser.parse_trades')
def test_app_simulation(mock_parse, mock_calc):
    mock_parse.return_value = {'pnl': [100]}
    mock_calc.return_value = {'balance': 11000}
    
    # This test is useless - it only tests that mocks are called
```

**Why this is bad:**
- Doesn't test actual parsing or calculation
- Tests implementation details, not behavior
- Breaks when refactoring
- Provides false confidence

**Fix:** Use real data instead:
```python
# GOOD: Real integration test
def test_app_simulation_real_data():
    with app.test_client() as client:
        with open('tests/test_data/sample.csv', 'rb') as f:
            response = client.post('/', data={'file': f, 'balance': 10000})
        
        assert response.status_code == 200
        assert b'Final Balance' in response.data
```

### ❌ Shallow Assertions

```python
# BAD: Only checks that something exists
def test_simulation_returns_data():
    result = run_simulation()
    assert result is not None
    assert 'final_balance' in result
    assert len(result['trajectories']) > 0
```

**Why this is bad:**
- Passes even if calculations are completely wrong
- Doesn't verify actual values
- Provides no confidence in correctness

**Fix:** Verify actual values:
```python
# GOOD: Verifies specific values
def test_simulation_with_known_outcomes(random_seed=42):
    """Test with fixed seed ensures deterministic results."""
    result = run_simulation(
        trade_stats={'pnl': [100, -50, 100]},
        initial_balance=1000,
        num_simulations=5,
        random_seed=42
    )
    
    # Verify actual calculated values (not just structure)
    assert 1000 < result['median_final_balance'] < 1200
    assert result['bankruptcy_probability'] == 0.0
    assert result['max_drawdown_pct'] < 10
```

### ❌ Synthetic Test Data That Hides Bugs

```python
# BAD: Alphabetically-sortable test data
test_data = [
    {'expiration': '2024-01-10', 'pnl': 100},
    {'expiration': '2024-01-20', 'pnl': -50},
    {'expiration': '2024-01-30', 'pnl': 75},
]
```

**Why this is bad:**
- Hides sorting bugs (alphabetical ≠ chronological)
- Too simple - doesn't expose edge cases
- Not representative of real data

**Fix:** Use real CSV files:
```python
# GOOD: Real data exposes sorting bugs
def test_trade_parsing_chronological_order():
    """Use real CSV with non-alphabetical dates."""
    trade_stats = parse_trade_csv('tests/test_data/real_trades.csv')
    
    # Verify dates are in chronological order (not alphabetical)
    dates = trade_stats['per_trade_dates']
    assert dates == sorted(dates)  # Would catch sorting bug
```

## Best Practices

### Use Real CSV Files

Keep representative CSV files in `tests/test_data/`:
- `sample_trades.csv` - Normal case, 10-20 trades
- `edge_case_dates.csv` - Non-alphabetical dates (2024-12-01, 2024-01-15, 2024-03-22)
- `missing_prices.csv` - Some trades with missing closing prices
- `all_losses.csv` - Edge case with no winning trades
- `single_trade.csv` - Minimal edge case

### Keep Tests Fast

- Use `num_simulations=5` or `num_simulations=10` (not 1000)
- Use `random_seed` for deterministic Monte Carlo tests
- Parallelize test execution with `pytest -n auto`

### Test Actual Values, Not Just Structure

```python
# BAD
assert len(result['trades']) > 0

# GOOD  
assert len(result['trades']) == 47  # Exact count from CSV
assert result['trades'][0]['date'] == '2020-07-28'  # First trade
assert abs(result['trades'][0]['pnl_pct'] - 73.9) < 0.1  # Actual value
```

### Golden File Tests

For complex calculations, maintain "golden file" tests:

```python
def test_known_trade_values():
    """Verify specific trades have expected calculated values."""
    trade_stats = parse_trade_csv('tests/test_data/golden.csv')
    
    # Trade 1: Known values from manual calculation
    assert trade_stats['per_trade_dates'][0] == '2024-01-15'
    assert abs(trade_stats['pnl_distribution'][0] - 125.50) < 0.01
    assert abs(trade_stats['theoretical_risks'][0] - 180.00) < 0.01
    
    # Trade 2: Another known case
    assert trade_stats['per_trade_dates'][1] == '2024-02-10'
    assert abs(trade_stats['pnl_distribution'][1] - (-95.25)) < 0.01
```

### Fail-Fast Validation

Don't use fallbacks or default values when data is invalid:

```python
# BAD: Silent fallback
risk_pct = (pnl / risk * 100) if risk > 0 else 0.0

# GOOD: Fail fast
if risk <= 0:
    raise ValueError(
        f"Invalid risk for trade on {date}: {risk}. "
        f"Check CSV for missing prices or invalid spread structure."
    )
risk_pct = (pnl / risk) * 100
```

### Document Why When Using Mocks

If you must use mocks, add a comment explaining why:

```python
@suppress_mock_warnings  # Alpaca API requires auth - not testable in CI
def test_historical_price_fetch():
    ...
```

## Test Organization

### Naming Conventions

- `test_integration.py` - End-to-end tests with real data
- `test_MODULE.py` - Unit tests for specific modules
- `test_data/` - Real CSV files for testing

### Test Structure

```python
class TestFeatureName:
    """Group related tests."""
    
    def test_normal_case(self):
        """Test typical usage."""
        ...
    
    def test_edge_case_empty_data(self):
        """Test with edge case: empty data."""
        ...
    
    def test_validation_error(self):
        """Test that invalid input raises clear error."""
        with pytest.raises(ValueError, match="Invalid risk"):
            ...
```

## Code Review Checklist

When reviewing tests, ask:
- [ ] Does this test use real data or synthetic data?
- [ ] If mocked, is mocking genuinely necessary? (Comment explains why?)
- [ ] Does it verify actual values or just structure?
- [ ] Would this test catch the bug it's meant to prevent?
- [ ] Is it deterministic (seeded RNG for Monte Carlo)?
- [ ] Does it test behavior, not implementation details?

## Running Tests

```bash
# Run all tests
tm_trade_analyzer_venv/bin/pytest

# Run with warnings visible
tm_trade_analyzer_venv/bin/pytest -v

# Run specific test file
tm_trade_analyzer_venv/bin/pytest tests/test_integration.py

# Run with coverage
tm_trade_analyzer_venv/bin/pytest --cov=. --cov-report=html

# Run in parallel (faster)
tm_trade_analyzer_venv/bin/pytest -n auto
```

## Target Metrics

- **Mock Ratio:** < 20% (prefer integration tests 4:1)
- **Coverage:** > 85% (but quality > quantity)
- **Test Speed:** Full suite < 10 seconds
- **Value Assertions:** Every test verifies at least one actual calculated value

## Examples

See these files for good patterns:
- `tests/test_integration.py` - Full end-to-end tests
- `tests/test_simulator.py` - Pure function unit tests
- `tests/test_trade_parser.py` - Real CSV parsing tests

## Summary

**Remember:**
1. Integration tests > Unit tests > Mocked tests
2. Real data > Synthetic data
3. Actual values > Structure checks
4. Fail fast > Silent fallbacks
5. Simple tests > Complex mocks

**When in doubt:** Write an integration test with real CSV data and `num_simulations=10`.
