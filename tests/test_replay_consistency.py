"""
Test to verify consistency between Position Size Plan (summary) and actual Replay results.

This covers two main issues:
1. Starting Risk % in summary should match the first trade's actual Risk %.
2. contract count in summary should match the first trade's executed contracts.

Both require the summary plan to use the first trade's specific risk metrics (replay mode)
rather than aggregate simulation metrics.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import simulator
import replay
import numpy as np
import pytest

def test_starting_risk_matches_first_trade_risk():
    """
    Verify that the Starting Risk % in position size plan matches
    the first trade's actual Risk % in replay details.
    
    If build_position_size_plan uses aggregate risk (p95 across all trades)
    to calculate starting_risk_pct, but replay uses the trade's specific risk,
    they will mismatch when first trade risk != aggregate risk.
    """
    # Create trade stats with varying theoretical risks
    # First trade has high risk (350), others have lower risk (180)
    per_trade_risks = [350.0] + [180.0] * 19
    per_trade_rewards = [50.0] * 20
    pnl_distribution = [50.0, -180.0] * 10
    per_trade_dates = [f'2023-{i+1:02d}-01' for i in range(20)]
    
    # Calculate p95 of risks - should be around 180 (since only 1 outlier)
    conservative_risk = float(np.percentile(per_trade_risks, 95))
    max_risk = float(max(per_trade_risks))
    
    trade_stats = {
        'num_trades': 20,
        'win_rate': 0.5,
        'conservative_theoretical_max_loss': conservative_risk,  # p95 approx 180
        'max_theoretical_loss': max_risk,  # max = 350
        'pnl_distribution': pnl_distribution,
        'per_trade_theoretical_risk': per_trade_risks,
        'per_trade_theoretical_reward': per_trade_rewards,
        'per_trade_dates': per_trade_dates
    }
    
    initial_balance = 5000
    target_risk_pct = 25.0
    
    # Build position size plan in REPLAY mode
    position_size_plan = simulator.build_position_size_plan(
        trade=trade_stats,
        initial_balance=initial_balance,
        position_sizing='percent',
        risk_calculation_method='conservative_theoretical',
        allow_exceed_target_risk=False,
        mode='replay'  # Use first trade's actual risk
    )
    
    # Find the 25% risk scenario in the plan
    scenario_25 = next((s for s in position_size_plan if s['target_risk_pct'] == 25.0), None)
    assert scenario_25 is not None, "25% risk scenario should exist in position size plan"
    
    # Run actual replay with same settings
    replay_result = replay.replay_actual_trades(
        trade_stats=trade_stats,
        initial_balance=initial_balance,
        position_sizing='percent',
        target_risk_pct=target_risk_pct,
        dynamic_risk_sizing=False,  # Static sizing based on initial balance
        risk_calculation_method='conservative_theoretical',
        allow_exceed_target_risk=False
    )
    
    # Get first trade details
    assert len(replay_result['trade_details']) > 0, "Should have at least one trade"
    first_trade = replay_result['trade_details'][0]
    
    # Assertions
    print(f"\nSummary Starting Risk %: {scenario_25['starting_risk_pct']:.2f}%")
    print(f"First Trade Risk %: {first_trade['risk_pct']:.2f}%")
    
    assert scenario_25['contracts'] == first_trade['contracts'], \
        f"Summary contracts {scenario_25['contracts']} should match first trade contracts {first_trade['contracts']}"
    
    assert abs(scenario_25['starting_risk_pct'] - first_trade['risk_pct']) < 0.01, \
        f"Summary starting risk {scenario_25['starting_risk_pct']:.2f}% should match first trade risk {first_trade['risk_pct']:.2f}%"


def test_fail_fast_when_replay_mode_missing_data():
    """
    Verify that mode='replay' fails fast when per_trade_theoretical_risk is missing.
    """
    # Trade stats WITHOUT per_trade_theoretical_risk
    trade_stats = {
        'num_trades': 20,
        'win_rate': 0.5,
        'conservative_theoretical_max_loss': 180.0,
        'max_theoretical_loss': 350.0,
        'pnl_distribution': [50.0] * 20
        # Missing: per_trade_theoretical_risk, per_trade_theoretical_reward, per_trade_dates
    }
    
    initial_balance = 5000
    
    # Should raise ValueError when mode='replay' but data is missing
    with pytest.raises(ValueError, match="mode='replay' requires 'per_trade_theoretical_risk'"):
        simulator.build_position_size_plan(
            trade=trade_stats,
            initial_balance=initial_balance,
            position_sizing='percent',
            risk_calculation_method='conservative_theoretical',
            allow_exceed_target_risk=False,
            mode='replay'  # This should fail fast
        )
    
    # Should work fine with mode='simulation' (uses aggregate)
    plan = simulator.build_position_size_plan(
        trade=trade_stats,
        initial_balance=initial_balance,
        position_sizing='percent',
        risk_calculation_method='conservative_theoretical',
        allow_exceed_target_risk=False,
        mode='simulation'  # Uses aggregate risk - works with synthetic data
    )
    
    assert len(plan) > 0, "Should successfully create plan with aggregate risk"


def test_starting_contracts_mismatch_affordability():
    """
    Verify that Starting Contracts in position size plan matches
    the first trade's contracts in replay details, even when limited by affordability.
    
    If aggregate risk > specific trade risk, summary might show fewer max affordable contracts
    than the replay actually executes, unless summary uses mode='replay'.
    """
    # Setup trade stats where aggregate risk (p95) is HIGHER than first trade's risk
    # First trade risk: 100
    # Other trades risk: 200 (aggregate p95 will be 200)
    per_trade_risks = [100.0] + [200.0] * 19
    per_trade_rewards = [50.0] * 20
    pnl_distribution = [50.0] * 20
    per_trade_dates = [f'2023-{i+1:02d}-01' for i in range(20)]
    
    trade_stats = {
        'num_trades': 20,
        'win_rate': 1.0,
        'conservative_theoretical_max_loss': 200.0,  # p95 = 200
        'max_theoretical_loss': 200.0,
        'pnl_distribution': pnl_distribution,
        'per_trade_theoretical_risk': per_trade_risks,
        'per_trade_theoretical_reward': per_trade_rewards,
        'per_trade_dates': per_trade_dates
    }
    
    # Set balance so that at high risk %, the contract count is limited by affordability
    # Balance = 1350
    # At 100% risk:
    #   Using aggregate (200): max_contracts = int(1350 / 200) = 6
    #   Using first trade (100): max_contracts = int(1350 / 100) = 13
    initial_balance = 1350
    risk_method = 'conservative_theoretical'
    
    # Build position size plan in REPLAY mode
    position_size_plan = simulator.build_position_size_plan(
        trade=trade_stats,
        initial_balance=initial_balance,
        position_sizing='percent',
        risk_calculation_method=risk_method,
        allow_exceed_target_risk=False,
        mode='replay'
    )
    
    # Find the 100% risk scenario (or highest available)
    scenario = next((s for s in position_size_plan if s['target_risk_pct'] == 100.0), None)
    if scenario is None:
        scenario = position_size_plan[-1]
    
    # Run replay
    replay_result = replay.replay_actual_trades(
        trade_stats=trade_stats,
        initial_balance=initial_balance,
        position_sizing='percent',
        target_risk_pct=scenario['target_risk_pct'],
        dynamic_risk_sizing=True,
        risk_calculation_method=risk_method,
        allow_exceed_target_risk=False
    )
    
    first_trade = replay_result['trade_details'][0]
    
    print(f"\nSummary Contracts: {scenario['contracts']}")
    print(f"First Trade Contracts: {first_trade['contracts']}")
    
    assert scenario['contracts'] == first_trade['contracts'], \
        f"Summary contracts {scenario['contracts']} != First trade contracts {first_trade['contracts']}"


if __name__ == '__main__':
    test_starting_risk_matches_first_trade_risk()
    test_starting_contracts_mismatch_affordability()
