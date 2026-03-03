# Test Coverage Analysis - Numeric Value Verification

## Executive Summary

**Current State:**
- ✅ 228 tests passing
- ✅ Excellent test quality (2.19% mock ratio)
- ✅ Good coverage for individual features
- ⚠️  **GAP: Missing systematic numeric verification across parameter combinations**

## Configuration Space

### Risk Calculation Methods (7)
1. `conservative_theoretical` - Variable, uses p95
2. `max_theoretical` - Variable, uses theoretical max
3. `median_realized` - Fixed, uses median historical loss
4. `average_realized` - Fixed, uses average historical loss
5. `average_realized_trimmed` - Fixed, uses trimmed mean
6. `fixed_conservative_theoretical_max` - Fixed, uses p95
7. `fixed_theoretical_max` - Fixed, uses theoretical max

### Reward Calculation Methods (17)
1. `no_cap` - No profit cap
2-5. `cap_25/40/50/75pct_conservative_theoretical_max`
6-9. `cap_25/40/50/75pct_theoretical_max`
10-13. `cap_25/40/50/75pct_average_realized`
14-17. `cap_25/40/50/75pct_conservative_realized_max`

### Other Parameters
- **Position Sizing:** Fixed contracts, Dynamic percent
- **Simulation Mode:** IID, Moving-block-bootstrap
- **Dynamic Risk Sizing:** True, False
- **allow_exceed_target_risk:** True, False

### Total Combinations
7 × 17 × 2 × 2 × 2 × 2 = **1,904 possible combinations**

## Current Test Coverage Analysis

### What We Have ✅

**test_simulator.py (99 tests):**
- ✅ Individual risk calculation methods tested
- ✅ Individual reward calculation methods tested
- ✅ Position sizing logic tested
- ✅ Bootstrap vs IID tested
- ✅ Some exact numeric value checks

**test_replay.py (26 tests):**
- ✅ Risk calculation methods tested with exact values
- ✅ Position sizing tested with exact balance calculations
- ✅ Per-trade details verified

**test_integration.py (4 tests):**
- ✅ End-to-end CSV → simulation flow
- ✅ Trajectory data structure verified
- Some numeric checks (initial balance = 10000)

**test_bootstrap_position_sizing.py (2 tests):**
- ✅ Bootstrap vs replay consistency tested
- ✅ Exact numeric alignment verified for one scenario

### What We're Missing ❌

1. **Systematic Risk Method Coverage:**
   - No tests verifying exact balances for `average_realized`
   - No tests verifying exact balances for `average_realized_trimmed`
   - Limited coverage for fixed vs variable method differences

2. **Reward Cap Interaction Testing:**
   - Only 5 reward cap methods tested (out of 16 cap methods)
   - No tests combining multiple risk methods × multiple reward caps
   - No verification that caps produce lower balances than no_cap

3. **Position Sizing Mode Coverage:**
   - Most tests use dynamic percent
   - Few tests verify fixed contracts with exact numeric values
   - No tests comparing fixed vs dynamic outcomes side-by-side

4. **Simulation vs Replay Consistency:**
   - Only one test (test_bootstrap_position_sizing) verifies bootstrap ≈ replay
   - No IID vs replay consistency tests
   - No tests verifying that same parameters → same position sizing decisions

5. **Risk Ceiling Enforcement:**
   - Limited tests for `allow_exceed_target_risk=False`
   - No verification that risk ceiling actually prevents trades
   - No tests showing exact contract counts respect risk ceiling

6. **Edge Case Numeric Verification:**
   - Bankruptcy scenarios tested, but not with exact final balance verification
   - High-risk scenarios tested, but not with precise expected ranges
   - No tests for "barely affordable" vs "clearly affordable" trades

## Recommended Test Coverage Plan

### Phase 1: Golden Path Test Matrix (High Priority)

Create a **test matrix** with exact numeric expectations for key combinations:

**File:** `tests/test_golden_values.py` (NEW)

**Structure:**
```python
@pytest.mark.parametrize("risk_method,reward_method,expected_range", [
    # Conservative + No Cap (baseline)
    ('conservative_theoretical', 'no_cap', (9500, 11500)),
    
    # Max theoretical (more aggressive)
    ('max_theoretical', 'no_cap', (9000, 12000)),
    
    # Median realized (fixed value)
    ('median_realized', 'no_cap', (9800, 11200)),
    
    # With reward caps (should be lower than no_cap)
    ('conservative_theoretical', 'cap_50pct_conservative_theoretical_max', (9200, 10800)),
    ('max_theoretical', 'cap_50pct_theoretical_max', (8800, 11000)),
    
    # Fixed methods
    ('fixed_conservative_theoretical_max', 'no_cap', (9600, 11400)),
    ('fixed_theoretical_max', 'no_cap', (9200, 11800)),
])
def test_simulation_exact_balance_ranges(risk_method, reward_method, expected_range):
    """Test that different risk/reward combinations produce expected balance ranges."""
```

**Coverage target:** 15-20 key combinations with exact numeric ranges

### Phase 2: Position Sizing Verification (High Priority)

**File:** `tests/test_position_sizing_numeric.py` (NEW)

**Tests needed:**
1. Fixed contracts: Verify exact contract count × P/L = balance change
2. Dynamic percent: Verify contract count = floor(balance × risk_pct / risk_per_contract)
3. Risk ceiling enforcement: Verify trades rejected when risk > ceiling
4. Fixed vs Dynamic comparison: Same balance → different contracts → different outcomes

**Example:**
```python
def test_fixed_contracts_exact_calculation():
    """Verify fixed contract sizing produces exact expected balances."""
    # 2 contracts, +$50 per contract = +$100
    # 2 contracts, -$100 per contract = -$200
    # Expected: $1000 → $1100 → $900 → exact sequence
    
def test_dynamic_percent_affordability_boundary():
    """Test trades at exact affordability boundary."""
    # Balance = $1000, risk = $180 per contract, 50% risk ceiling
    # Max risk = $500, affordable contracts = 2 (2×180=$360 < $500)
    # Try to take 3 contracts (3×180=$540 > $500) → should reject
```

### Phase 3: Simulation vs Replay Consistency (Medium Priority)

**File:** `tests/test_simulation_replay_consistency.py` (NEW)

**Tests needed:**
1. Bootstrap with block_size = len(trades) should match replay exactly
2. IID mode should produce results within replay's distribution
3. Same risk_calculation_method → same position sizing decisions

**Example:**
```python
def test_bootstrap_full_sequence_matches_replay():
    """Bootstrap with block_size=all trades should match replay exactly."""
    # Run replay
    # Run bootstrap with block_size = num_trades (forces exact sequence)
    # Assert final_balance exactly matches
```

### Phase 4: Reward Cap Validation (Medium Priority)

**File:** `tests/test_reward_cap_effects.py` (NEW)

**Tests needed:**
1. Verify capped reward < uncapped reward (monotonicity)
2. Verify different cap percentages produce ordered results (25% < 50% < 75% < no_cap)
3. Verify caps apply per-contract correctly
4. Verify historical P/L not capped in bootstrap mode

**Example:**
```python
def test_reward_cap_monotonicity():
    """Verify increasing cap percentage → increasing final balance."""
    balance_25 = simulate(reward='cap_25pct_conservative_theoretical_max')
    balance_50 = simulate(reward='cap_50pct_conservative_theoretical_max')
    balance_75 = simulate(reward='cap_75pct_conservative_theoretical_max')
    balance_no = simulate(reward='no_cap')
    
    assert balance_25 <= balance_50 <= balance_75 <= balance_no
```

### Phase 5: Risk Method Differences (Low Priority)

**File:** `tests/test_risk_method_differences.py` (NEW)

**Tests needed:**
1. Verify conservative < max (conservative uses p95, max uses 100th percentile)
2. Verify fixed methods use same value for all trades
3. Verify variable methods adjust per-trade
4. Verify average_realized and average_realized_trimmed produce different results

## Implementation Priority

### Must Have (Blocks Production Confidence)
1. ✅ Golden path test matrix (Phase 1) - 15-20 tests
2. ✅ Position sizing verification (Phase 2) - 8-10 tests
3. ✅ Sim vs replay consistency (Phase 3) - 3-5 tests

### Should Have (Improves Robustness)
4. Reward cap validation (Phase 4) - 6-8 tests
5. Risk method differences (Phase 5) - 5-7 tests

### Total New Tests Needed: 37-50 tests

## Expected Outcomes

**After completing this plan:**
- ✅ 265-278 total tests (from 228)
- ✅ All major parameter combinations have numeric verification
- ✅ Exact expected values documented for reference scenarios
- ✅ Regression protection for critical interactions
- ✅ Clear evidence that simulations produce correct numeric results
- ✅ Documentation of expected behaviors across configuration space

## Notes

- Use `np.random.seed(42)` for all deterministic tests
- Use `num_simulations=10` for speed
- Use real CSV from `tests/test_data/test_call_spread.csv` when possible
- Document **why** each expected range is correct (comments in test)
- When exact values impossible, use tight ranges (±5%)
