# AGENT PROMPT: Add Numeric Value Verification Tests

## Context

The project has excellent test quality (228 tests, 2.19% mock ratio) but lacks **systematic numeric verification** across parameter combinations. We need to add exact/near-exact balance verification tests to ensure correctness across:
- 7 risk calculation methods
- 17 reward calculation methods  
- 2 position sizing modes
- 2 simulation modes (IID, bootstrap)
- Both simulation AND replay

See `TEST_COVERAGE_ANALYSIS.md` for detailed gap analysis.

## Your Task

Implement **Phase 1 (Golden Path Test Matrix)** - the highest priority tests with exact numeric expectations.

## Requirements

### 1. Create `tests/test_golden_values.py`

Add 15-20 parameterized tests that verify exact balance ranges for key combinations of:
- `risk_calculation_method` 
- `reward_calculation_method`
- Initial balance, position sizing mode

**Must verify:**
- Conservative + no_cap (baseline)
- Max_theoretical + no_cap (more aggressive)  
- Median_realized + no_cap (fixed value)
- Conservative + 50% cap (should be lower than no_cap)
- Max_theoretical + 50% cap
- Fixed methods (should use same value for all trades)

**Use this pattern:**
```python
@pytest.mark.parametrize("risk_method,reward_method,expected_range", [
    # Test cases with expected balance ranges
])
def test_simulation_exact_balance_ranges(risk_method, reward_method, expected_range):
    """Test different risk/reward combinations produce expected balances."""
    csv_path = 'tests/test_data/test_call_spread.csv'
    trade_stats = parse_trade_csv(csv_path)
    
    np.random.seed(42)  # CRITICAL: Deterministic
    result = run_monte_carlo_simulation(
        trade_stats=trade_stats,
        initial_balance=10000,
        num_simulations=10,  # Small for speed
        position_sizing='percent',
        dynamic_risk_sizing=True,
        simulation_mode='iid',
        risk_calculation_method=risk_method,
        reward_calculation_method=reward_method
    )
    
    median_final = result[0]['table_rows'][X]['Median Final $']
    # Parse and verify within expected_range
```

### 2. Add Position Sizing Numeric Tests

In same file or `tests/test_position_sizing_numeric.py`, add 8-10 tests:

**Fixed Contracts:**
```python
def test_fixed_contracts_exact_calculation():
    """Verify fixed contract sizing produces exact expected balances.
    
    With 2 contracts fixed:
    - Trade 1: +$50/contract × 2 = +$100 → Balance: $1000 → $1100
    - Trade 2: -$100/contract × 2 = -$200 → Balance: $1100 → $900
    """
    # Test exact sequence
```

**Dynamic Percent - Affordability Boundary:**
```python
def test_dynamic_percent_affordability_boundary():
    """Test trades at exact affordability boundary.
    
    Balance=$1000, risk=$180/contract, 50% ceiling → max_risk=$500
    Affordable: 2 contracts (2×$180=$360 < $500) ✅
    Not affordable: 3 contracts (3×$180=$540 > $500) ❌
    """
    # Test that 2 contracts taken, not 3
```

**Risk Ceiling Enforcement:**
```python
def test_risk_ceiling_prevents_trades():
    """Verify allow_exceed_target_risk=False prevents trades."""
    # Low balance + high risk per contract → should reject trades
    # Verify final_balance ≈ initial_balance (no trades taken)
```

### 3. Add Simulation vs Replay Consistency Test

```python
def test_bootstrap_full_sequence_matches_replay_exactly():
    """Bootstrap with block_size=all trades must match replay exactly.
    
    When bootstrap samples with block_size = len(trades), it should
    produce the exact historical sequence → same results as replay.
    """
    csv_path = 'tests/test_data/test_call_spread.csv'
    trade_stats = parse_trade_csv(csv_path)
    
    # Run replay
    replay_result = replay_actual_trades(
        trade_stats=trade_stats,
        initial_balance=10000,
        position_sizing='percent',
        target_risk_pct=10.0,
        dynamic_risk_sizing=True,
        risk_calculation_method='conservative_theoretical'
    )
    
    # Run bootstrap with full block size (forces exact sequence)
    sim_result = run_monte_carlo_simulation(
        trade_stats=trade_stats,
        initial_balance=10000,
        num_simulations=1,  # Single run
        simulation_mode='moving-block-bootstrap',
        block_size=trade_stats['num_trades'],  # Full sequence
        num_trades=trade_stats['num_trades'],
        position_sizing='percent',
        dynamic_risk_sizing=True,
        risk_calculation_method='conservative_theoretical',
        random_seed=42
    )
    
    # Extract final balance from simulation
    # Assert: abs(sim_final - replay_final) < $1 (floating point tolerance)
```

## Critical Rules

1. **TDD:** Write the test FIRST, then verify it passes with existing code
2. **Always use `np.random.seed(42)`** for Monte Carlo tests
3. **Use `num_simulations=5-10`** for speed (not 1000)
4. **Use real CSV:** `tests/test_data/test_call_spread.csv`
5. **Verify exact values or tight ranges (±5%)**
6. **Add comments explaining WHY each expected value is correct**
7. **Run tests after each addition:** `tm_trade_analyzer_venv/bin/pytest tests/test_golden_values.py -v`

## How to Determine Expected Values

For each test case:

1. **Run the simulation manually first** to see actual output
2. **Verify the output makes logical sense:**
   - Capped rewards < uncapped rewards
   - More aggressive risk methods → wider variance
   - Fixed methods → consistent behavior
3. **Document why this range is expected** in test comment
4. **Use ranges, not exact values:** `(9500, 11500)` not `10432.17`

## Example Test Structure

```python
"""
Golden path tests for numeric value verification.

These tests verify that different parameter combinations produce
expected balance outcomes within documented ranges.
"""

import pytest
import numpy as np
import os
from trade_parser import parse_trade_csv
from simulator import run_monte_carlo_simulation
from replay import replay_actual_trades


class TestGoldenPathBalanceRanges:
    """Test exact balance ranges for key parameter combinations."""
    
    @pytest.fixture
    def test_trade_stats(self):
        """Load test CSV once for all tests."""
        csv_path = os.path.join(
            os.path.dirname(__file__),
            'test_data',
            'test_call_spread.csv'
        )
        return parse_trade_csv(csv_path)
    
    @pytest.mark.parametrize("risk_method,reward_method,expected_min,expected_max", [
        # Baseline: Conservative + No Cap
        ('conservative_theoretical', 'no_cap', 9500, 11500),
        
        # TODO: Add 14-19 more cases
    ])
    def test_balance_range_for_combination(
        self, test_trade_stats, risk_method, reward_method, expected_min, expected_max
    ):
        """Verify balance falls within expected range."""
        np.random.seed(42)
        
        result = run_monte_carlo_simulation(
            trade_stats=test_trade_stats,
            initial_balance=10000,
            num_simulations=10,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            risk_calculation_method=risk_method,
            reward_calculation_method=reward_method
        )
        
        # Extract median final balance
        # (Implementation depends on result structure)
        
        assert expected_min <= median_final <= expected_max, (
            f"Balance ${median_final:.0f} outside expected range "
            f"[${expected_min}, ${expected_max}] for {risk_method} + {reward_method}"
        )
```

## Deliverables

1. ✅ `tests/test_golden_values.py` with 15-20 parameterized tests
2. ✅ Position sizing numeric verification tests (8-10 tests)
3. ✅ Bootstrap vs replay consistency test (1 test)
4. ✅ All tests passing with existing code
5. ✅ Test count increases from 228 to ~250-260

## Success Criteria

- Run `tm_trade_analyzer_venv/bin/pytest` - all tests pass
- New tests verify **exact numeric values or tight ranges**
- New tests use **real data** (no mocks)
- New tests are **deterministic** (seeded RNG)
- **Total test count: 250-260** (was 228)

## If You Get Stuck

1. Start with 3-5 simple cases to establish pattern
2. Run tests frequently to catch issues early
3. If ranges are wrong, investigate why (don't just widen range)
4. Document any unexpected findings in test comments

## After Completion

Update `TEST_COVERAGE_ANALYSIS.md` with:
- ✅ Phase 1 Complete
- Test count: X tests added
- Any issues discovered during implementation
